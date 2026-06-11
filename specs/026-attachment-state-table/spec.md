# Feature Specification: Analysis-owned attachment state table

**Feature Branch**: `026-attachment-state-table`
**Created**: 2026-06-11
**Status**: Draft
**Input**: User description: "Move analysis-owned classification state off the mirror table attachments into a new analysis-owned attachment_state table (classified_at), and remove the analysis-side content_hash backfill so only the scraper writes attachments (fixes BUG-002, issue #33)"

## Context

`entries`, `attachments`, and `accountability_reports` are meant to be an **exact copy** of what was scraped from the brcondos portal. Everything the auditing pipeline derives — alerts, documents, analyses — is our own and lives in its own tables. Today the analysis pipeline mutates the mirror table `attachments` in three places, so the table is part mirror, part pipeline scratch space:

1. The pipeline stamps `attachments.classified_at` after each attachment's analysis is written.
2. The `mark-pending` operation clears `attachments.classified_at` to re-queue work.
3. The pipeline backfills `attachments.content_hash` for legacy rows that were scraped before that column existed.

This breaks the mirror guarantee: you cannot diff `attachments` against a fresh scrape to detect portal-side changes or forgery, because our own pipeline legitimately mutates the table. It also makes the scraper and analysis race on the same rows (the scraper's full-row replace wipes analysis state), and the schema cannot express ownership.

## Clarifications

### Session 2026-06-11

Running unattended (no interactive questioning); ambiguities resolved by documented assumption rather than questions. The two highest-impact decisions:

- Q: Where does the classification state live, and is `content_hash` moved too? → A: A new analysis-owned table keyed by attachment id holds `classified_at`; `content_hash` stays on `attachments` as scraper-owned, only its analysis-side backfill is removed (see Assumptions).
- Q: How is existing state preserved on upgrade? → A: The migration copies current `attachments.classified_at` into the new table before dropping the column; `content_hash` values are left in place (FR-008, FR-009).

All remaining taxonomy categories are Clear in the spec; see the Assumptions section for the full set of resolved defaults.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Mirror table is verifiable against a fresh scrape (Priority: P1)

An auditor (or a future forgery-detection job) wants to trust that the mirror table `attachments` contains exactly what the portal returned, so it can diff a stored snapshot against a fresh scrape and treat any difference as a portal-side change worth investigating.

**Why this priority**: This is the core invariant the bug violates and the whole reason the feature exists. Without it, the forgery-detection goal of the project is unverifiable on this table.

**Independent Test**: Run the full classification + analysis pipeline against a period, then confirm that no row in `attachments` was modified by the pipeline (the rows are byte-identical to what the scraper wrote). Re-scraping the same period without portal changes leaves analysis state intact.

**Acceptance Scenarios**:

1. **Given** a period whose attachments have been scraped, **When** the analysis pipeline classifies and analyzes them, **Then** the `attachments` rows are unchanged (only an analysis-owned state record is created/updated).
2. **Given** classified attachments, **When** the scraper re-runs for the same period (full-row replace), **Then** the classification state survives the re-scrape (it does not live on the replaced row).
3. **Given** a stored snapshot of `attachments` and a fresh identical scrape, **When** the two are diffed, **Then** there are zero differences attributable to the analysis pipeline.

---

### User Story 2 - Work selection still drives classification (Priority: P1)

The classification pipeline must continue to select "pending" attachments (those not yet classified), stamp them as classified when their analysis is written, and let an operator re-queue a subset for re-classification — exactly as today, but reading and writing the analysis-owned state instead of the mirror table.

**Why this priority**: The pending-set selection (`docs-plan`), the classified stamp (`apply-extractions`), and the re-queue (`mark-pending`) are the backbone of the classification loop. The feature must preserve their behavior end-to-end, or the pipeline stops working.

**Independent Test**: With a freshly scraped period (no state rows yet), `docs-plan` lists all attachments as pending; after `apply-extractions`, they are no longer pending; `mark-pending` for a subset returns exactly that subset to pending on the next plan.

**Acceptance Scenarios**:

1. **Given** a freshly scraped attachment with no state record, **When** the plan is computed, **Then** the attachment is treated as pending (needs classification).
2. **Given** an attachment whose analysis was just written, **When** the plan is computed again, **Then** the attachment is treated as classified (excluded from the pending set).
3. **Given** a classified attachment, **When** the operator marks it pending, **Then** the next plan treats it as pending again.
4. **Given** the analysis writeback fails mid-batch, **When** the operator inspects the attachment, **Then** it is still pending (the classified stamp must not commit without the analysis rows — self-healing on re-run is preserved).

---

### User Story 3 - Only the scraper owns content_hash (Priority: P2)

The shared-NF grouping key (`content_hash`) is derived from scraped page bytes and is written by the scraper at scrape time. Legacy rows scraped before the column existed must still get a hash, but that backfill must be the scraper's responsibility, not the analysis pipeline's — so the rule becomes simple: only the scraper writes `attachments`.

**Why this priority**: It removes the last analysis-side write to the mirror table. Grouping continues to work (it reads `content_hash`, with the existing in-memory fallback for rows still missing one), so this is important for the invariant but not blocking the core classification loop.

**Independent Test**: Run the analysis pipeline against a period that contains a legacy attachment with a NULL `content_hash`; confirm the pipeline issues no write to `attachments`, grouping still works for that period (via the in-memory hash fallback), and the scraper's image-download path populates the missing `content_hash`.

**Acceptance Scenarios**:

1. **Given** an attachment with a NULL `content_hash`, **When** the analysis pipeline runs, **Then** it performs no write to `attachments` (the hash is computed in memory for this run's grouping only).
2. **Given** an attachment with a NULL `content_hash`, **When** the scraper's image-download path runs for it, **Then** the scraper populates `content_hash` (the existing scraper-owned backfill path is the only writer).
3. **Given** a period where every attachment already has a `content_hash`, **When** the analysis pipeline runs, **Then** behavior and grouping are identical to today.

---

### Edge Cases

- **Existing classified rows on upgrade**: attachments already stamped with `classified_at` on the mirror table before this change must remain classified after the migration (their state is carried over, not lost — otherwise the whole corpus re-classifies).
- **Existing content_hash values**: hashes already stored on the mirror table by the scraper must be preserved as-is (they are scraper-owned and stay where they are).
- **State record for a deleted attachment**: if an attachment row is ever removed, an orphaned state record must not break the plan (it simply has nothing to join to).
- **Atomicity**: the classified stamp must be written in the same atomic unit as the analysis rows, so a partial failure leaves the attachment pending rather than stamped-but-empty.
- **Re-scrape**: a full-row replace of an attachment by the scraper must not disturb the separate analysis state record.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST store the per-attachment classification state (the "classified" timestamp / pending flag) in an analysis-owned location that is separate from the mirror table `attachments`.
- **FR-002**: The analysis pipeline MUST NOT issue any write (insert/update/delete) to the mirror table `attachments`.
- **FR-003**: The work-selection plan MUST treat an attachment as **pending** when it has no classification state recorded (i.e. never classified, or explicitly re-queued), and as **classified** otherwise — preserving today's "pending = not yet classified" semantics.
- **FR-004**: When an attachment's rolled-up analysis is written, the system MUST record its classification state atomically with the analysis rows, so a failed analysis write leaves the attachment pending (no stamped-but-empty state).
- **FR-005**: The re-queue operation (`mark-pending`) MUST return the selected attachments to pending by updating the analysis-owned state, without touching the mirror table.
- **FR-006**: The shared-NF grouping key (`content_hash`) MUST continue to be read for grouping, with the existing in-memory fallback for rows that still lack one, but the analysis pipeline MUST NOT persist any `content_hash` write to `attachments`.
- **FR-007**: Backfilling a missing `content_hash` MUST be owned by the scraper's image-handling path (the same path that already populates `file_path` and `content_hash` for rows missing images), not by the analysis pipeline.
- **FR-008**: On upgrade, existing classification state currently held on `attachments` MUST be carried over to the new analysis-owned location, so already-classified attachments are not re-classified.
- **FR-009**: Existing `content_hash` values held on `attachments` MUST be preserved (scraper-owned; not moved).
- **FR-010**: The end-to-end classification loop (plan → classify → apply → analyze → mismatches, plus the re-queue and the self-improving loop's re-run) MUST behave identically to today from the operator's perspective.

### Key Entities *(include if feature involves data)*

- **Attachment (mirror)**: the multi-page bundle downloaded from the portal, one per ledger entry. After this change it carries only scraped fields and is written exclusively by the scraper. `content_hash` (the shared-NF grouping key, derived from scraped bytes) stays here as a scraper-owned field.
- **Attachment classification state (analysis-owned)**: a per-attachment record, keyed by the attachment's identifier, holding the classification timestamp / pending status. Created/updated by the analysis pipeline; the absence of a record (or a cleared one) means "pending". Independent of the mirror row's lifecycle.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: After a full classification + analysis run over a period, **zero** rows in `attachments` differ from what the scraper wrote (100% of pipeline-attributable mutations eliminated).
- **SC-002**: The pending-set selection, classified-stamp, and re-queue operations produce the same observable results as before the change for a representative period (same set of pending attachments at each step).
- **SC-003**: A period that was fully classified before the change remains fully classified after the upgrade (0% spurious re-classification of already-done work).
- **SC-004**: Shared-NF grouping produces the same groups as before for a representative period (no change in reconciliation outcomes), including for rows whose `content_hash` was NULL.

## Assumptions

- **Single-writer rule chosen over moving content_hash**: the issue offers two options for `content_hash` (move it to the state table, or keep it on `attachments` and move the backfill to the scraper). This spec adopts the latter — `content_hash` is derived from scraped bytes and is already written by the scraper at scrape time, so it is legitimately scraper-owned; only the analysis-side backfill is removed. This minimizes churn and keeps grouping reads on the same column.
- **content_hash backfill is already covered by the scraper**: the scraper's image-download path already computes and writes `content_hash` for rows it (re)downloads images for, so removing the analysis-side backfill does not strand legacy rows that ever get their images (re)materialized by the scraper. For a run where a legacy row's hash is still NULL, the existing in-memory fallback keeps grouping correct for that run.
- **No UI/API impact**: `classified_at` and `content_hash` are analysis-internal; no Next.js API route or dashboard component reads them, so there is no frontend change.
- **State location is a new analysis-owned table** keyed by attachment id (1:1 with `attachments`), matching the issue's suggested `attachment_state` shape, holding the classification timestamp. The mirror-table `classified_at` column is dropped once its values are carried over.
- **Local-first verification**: the change is verified against the local D1 (prod-like data) via the running app and the pipeline CLIs; production migration is applied separately by an operator.
