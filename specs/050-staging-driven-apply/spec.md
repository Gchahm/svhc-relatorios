# Feature Specification: Staging-driven apply-extractions (safety + per-attachment scoping)

**Feature Branch**: `050-staging-driven-apply`
**Created**: 2026-06-13
**Status**: Draft
**Input**: GitHub issue #84 — TRIAGE-001. Make `apply-extractions` staging-driven: only roll up shared-NF groups whose representative attachment has `page_classifications` staging rows, so a pending attachment with no staging is skipped (left intact) instead of overwritten with an empty analysis — this is both the safety guard and the per-attachment scoping mechanism. No schema change, no migration.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Re-running apply never destroys a good analysis (Priority: P1)

An operator re-runs the period's `apply-extractions` (a full pass over the period, or as part of an autonomous loop). Some attachments in the period are *pending* — `attachment_state.classified_at IS NULL` — but their per-page staging rows in `page_classifications` were already consumed (pruned) by an earlier successful apply (feature 035), or their vision step crashed before recording any staging. With today's behaviour these attachments are visited, produce an all-empty extraction, and the empty roll-up **overwrites** the prior good analysis and stamps the attachment classified. After this change, an attachment whose group representative has no staging rows is simply **not processed** — its existing analysis is left intact and it remains pending, self-healing on a real future classification.

**Why this priority**: This is the blocking safety hazard. It makes autonomous re-runs of the pipeline unsafe and forces a fragile manual "isolate the pending set" workaround (project memory `pending-without-staging-destructive`; runbook `fix-document-vision-mismatch.md` Problem #2). Losing a correct analysis is data loss and can flip a true finding into a false one.

**Independent Test**: Seed a period with a pending, paged attachment that has an existing analysis but no staging rows; run `apply-extractions`; assert the analysis and its records are unchanged and the attachment is still pending.

**Acceptance Scenarios**:

1. **Given** a pending attachment with an existing `attachment_analyses` row and **no** `page_classifications` staging rows, **When** `apply-extractions` runs over its period, **Then** the existing analysis row and its records are unchanged and the attachment remains pending (no `classified_at` stamp written).
2. **Given** a pending attachment whose representative **has** staging rows, **When** `apply-extractions` runs, **Then** its analysis is rebuilt from the staging rows and written exactly as before this change.

---

### User Story 2 - Targeted single-attachment reclassify touches only that attachment's group (Priority: P2)

An operator (or the future triage agent) wants to re-classify exactly one attachment X after correcting its vision extraction. They record X's per-page staging rows (`record-classification`) and run `apply-extractions`. Only X's shared-NF group is rolled up and written; every other attachment in the period — including other pending attachments without staging — is untouched. No global pending-set mutation, no id flags through the CLI.

**Why this priority**: This is the scoping benefit that the safety change unlocks: "select for apply = record staging". It removes the manual pending-set isolation step entirely. It depends on US1's mechanism being in place.

**Independent Test**: Seed a period with two pending paged attachments; record staging for only one of them; run `apply-extractions`; assert only the one with staging gets a (re)built analysis + classified stamp, and the other is untouched.

**Acceptance Scenarios**:

1. **Given** two pending paged attachments in different NF groups and staging rows recorded for only attachment X's representative, **When** `apply-extractions` runs, **Then** X's group is rolled up and stamped classified, and the other attachment is left pending with no analysis written.

---

### Edge Cases

- **Shared-NF group, staging only on the representative**: siblings carry no staging and inherit the representative's extraction via fan-out. The selection check MUST key off the **group representative**, so a group whose representative has staging is fully processed (representative + all siblings), and a group whose representative has none is fully skipped. (Within the current pipeline only representative pages are ever classified, so siblings never independently carry staging.)
- **Group representative with a recorded error staging row**: a staging row that is an `{"error": ...}` result still counts as "has staging" — the attachment was visited and recorded — so the group is processed and the existing per-page-error roll-up behaviour (a recorded error does not abort the attachment) is preserved. Only the *absence* of any staging row skips a group.
- **Period with no staging rows at all**: `apply-extractions` processes zero groups and writes nothing; no error.
- **Partial staging across a representative's pages**: a representative with staging for some but not all of its pages still counts as "has staging" and is processed; missing pages remain recorded as per-page errors exactly as today.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: `apply-extractions` MUST process **only** the shared-NF groups whose **representative attachment** has at least one row in the `page_classifications` staging table; a group whose representative has no staging row MUST be skipped entirely (representative and all siblings).
- **FR-002**: A skipped group's attachments MUST NOT be written, deleted, overwritten, or stamped classified — their existing `attachment_analyses` rows, `attachment_analysis_records`, and `attachment_state` rows are left exactly as they were.
- **FR-003**: The staging-presence check MUST be group-aware (keyed off the representative attachment id), NOT a naïve per-row filter that would drop siblings of a processed group (siblings own no staging and must still be fanned out).
- **FR-004**: A processed group's behaviour MUST be byte-identical to the prior behaviour — same roll-up, group reconciliation, sibling fan-out, entry validation, atomic delete-then-insert write, `classified_at` stamp, and staging prune.
- **FR-005**: The vision/plan phases MUST be unchanged — `docs-plan` (`plan_extractions`), the loader's pending query, `mark-pending`, `classify-period`, and `improve-classification` keep using the pending set (`classified_at IS NULL`). Only `apply`'s group selection changes.
- **FR-006**: There MUST be no D1 schema change and no migration. The staging-presence signal is read from the existing `page_classifications` rows already loaded into the period payload by the loader.
- **FR-007**: When `apply-extractions` processes zero groups (no staging anywhere in scope), it MUST complete without error and without writing anything.

### Key Entities *(include if feature involves data)*

- **page_classifications (staging table)**: one row per `(attachment_id, page_label)` recorded by the vision skill. Its **presence** for a group's representative attachment id is the selection signal for `apply`. Read-only here (no new columns).
- **Shared-NF group**: a set of attachments sharing byte-identical page content (`attachments.content_hash`), with a single representative (highest-amount member); the representative's extraction is fanned out to siblings.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Re-running `apply-extractions` over a period never overwrites or deletes an existing analysis whose group representative lacks staging rows (verified by an integration test: analysis row + records unchanged, attachment still pending).
- **SC-002**: A targeted single-attachment reclassify (record one attachment's staging, then apply) writes/updates exactly one group's analyses and touches no other attachment (verified by an integration test).
- **SC-003**: For every group whose representative has staging, the produced `attachment_analyses` are identical to the pre-change output (no regression; covered by existing apply/merge tests continuing to pass).
- **SC-004**: The manual "isolate the pending set" step in the document-fix runbook is no longer required for a scoped reclassify (the procedure reduces to: record staging → apply).

## Assumptions

- **Representative-keyed check is sufficient.** In the current pipeline only the representative's pages are ever classified (the plan lists only representative pages; siblings inherit via fan-out). So "the representative has staging" is the correct and complete selection signal; no need to inspect sibling staging. (Recorded in FR-003.)
- **Staging rows are already loaded per period.** `load_all_periods` puts the period's `page_classifications` rows in `PeriodData.raw["page_classifications"]` (the same source `build_plan`'s `recorded` flag and the `D1ExtractionProvider` already use). The selection check reuses this in-memory list — no extra D1 read.
- **An error staging row counts as present.** A representative whose only staging is an `{"error": ...}` result is still "classified" (it was visited and recorded), so its group is processed; this preserves the existing recorded-error roll-up path. Absence of *any* row is the only skip condition.
- **No change to `docs-plan` output.** `build_plan` still lists all pending groups (its `recorded` flag already tells the classify skill which pages still need a page recorded). The apply-side selection is applied when iterating the envelopes in `apply_extractions`, not by changing `build_plan`.
