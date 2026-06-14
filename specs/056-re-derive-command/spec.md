# Feature Specification: Re-derive command (run mappers over stored transcriptions; no vision)

**Feature Branch**: `056-re-derive-command`
**Created**: 2026-06-14
**Status**: Draft
**Input**: EXTRACT-005 (issue #90) — re-derive CLI command: run the EXTRACT-003 deterministic mappers over stored typed transcriptions to rebuild `attachment_analyses` roll-ups, then `build-documents` and `analyze` — image-free, no vision; scoped (period/attachment) and global; idempotent; honors `--remote`.

## Overview

When a reconciliation finding is caused by the **deterministic mapper** picking the wrong field (e.g. an NFS-e total that should read `valor_liquido` but the mapper read `valor_total`), the root cause is in code, not in the transcription. The page was read correctly; the rule that interprets it was wrong. After the mapper is fixed, the corrected interpretation must be propagated to every already-classified document **without re-reading any page image** — the rich typed transcriptions are already stored in the database (`attachment_analysis_records.response`, EXTRACT-004).

This feature adds a **`re-derive`** CLI command: it re-runs the (now-fixed) deterministic mappers over the **stored** typed transcriptions, rebuilds the authoritative `attachment_analyses` roll-ups, rebuilds the global documents entity, and refreshes alerts — all **image-free** (zero vision calls, no R2 image reads). It is the systematic-fault branch of the triage decision tree (design doc §10.5): *"transcription right, mapper wrong → fix the deterministic mapper + RE-DERIVE."* It is the propagation path parallel to `apply-extractions`, but it sources extractions from the persisted analysis records rather than from fresh vision.

## Clarifications

### Session 2026-06-14

Run unattended (no interactive answerer). An internal ambiguity scan found no critical, blocking ambiguities — the material decisions were resolved as documented assumptions rather than as blocking questions:

- Q: Where does re-derive read the stored transcription from — `page_classifications` staging or `attachment_analysis_records.response`? → A: `attachment_analysis_records.response` (staging is pruned after apply, feature 035; the durable copy lives in the records table — see Assumptions).
- Q: Does re-derive invent a parallel roll-up path or reuse the staging-driven apply? → A: Reuse the feature-050 staging-driven `apply_extractions` via the `corrections._propagate` primitive (reconstruct staging → clear stamp → apply → `run_analysis`), so roll-ups are byte-for-byte consistent and inherit the no-empty-overwrite safety guard (see Assumptions).
- Q: When both `--periodo` and `--attachment-id` are given, union or intersection? → A: Intersection (named attachments restricted to named periods) — see Edge Cases / Assumptions.
- Q: Does FR-004 need a separate `build-documents` call, or does `run_analysis` cover it? → A: `run_analysis` already rebuilds documents before writing alerts, so one `run_analysis` over the affected periods covers FR-004 (see Assumptions).

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Systematic mapper fix corrects all affected documents (Priority: P1)

An engineer fixes a deterministic mapper (a one-line change in `type_mappers.py`) that was picking the wrong reconciliation field for a document type. Many documents of that type carry a now-stale `attachment_analyses` roll-up. The engineer runs `re-derive` once; every affected document's reconciliation fields (`extracted_amount`, `amount_match`, issuer, date, etc.) are recomputed from the stored transcription using the corrected mapper, and the spurious findings clear — with **zero** vision/image cost.

**Why this priority**: This is the entire purpose of the feature and the acceptance criterion of the issue. Without it, a systematic mapper fix requires either an expensive full re-classification (re-vision of every page) or per-document hand correction.

**Independent Test**: Seed a period with at least one document whose stored transcription is typed and whose current roll-up was produced by a mapper that has since been "fixed". Run `re-derive --periodo <p>`. Verify the rebuilt `attachment_analyses` reflects the corrected mapper output and the corresponding finding is gone, with no R2 image read performed.

### User Story 2 - Scoped re-derive (Priority: P2)

An engineer wants to re-derive only a single period, or only specific attachments, rather than the whole corpus (e.g. to verify a fix on a representative period before a full run, or to limit blast radius). They pass `--periodo <p>` and/or `--attachment-id <ids…>`; only the in-scope attachments are rebuilt, and everything else is left untouched.

**Why this priority**: Scoping bounds the cost and risk of a re-derive and lets an engineer validate a fix incrementally. The issue lists "Scoped (period/attachment) and global" as a requirement.

**Independent Test**: Seed two periods. Run `re-derive --periodo <p1>`; verify only `p1`'s analyses changed and `p2`'s are byte-identical. Run `re-derive --attachment-id <one id>`; verify only that attachment's NF group changed.

### User Story 3 - Global re-derive (Priority: P2)

With no scope flags, `re-derive` rebuilds every already-classified attachment across all periods in one run, then rebuilds the global documents entity and refreshes alerts for every affected period.

**Why this priority**: A mapper fix is systematic — it usually affects documents across many periods. The global run is the common case after a code fix lands.

**Independent Test**: Seed multiple periods. Run `re-derive` (no flags). Verify analyses across all periods are rebuilt from stored transcriptions, documents are rebuilt, and alerts are refreshed.

### User Story 4 - Idempotent and safe (Priority: P1)

Running `re-derive` twice in a row with no mapper change between runs produces identical database state (the second run is a no-op in effect). A re-derive never reads a page image, never calls vision, and never overwrites a good roll-up with an empty one when the stored transcription is intact.

**Why this priority**: Idempotency is an explicit acceptance criterion; safety (no destructive empty overwrite) is the load-bearing invariant inherited from the staging-driven apply (feature 050).

**Independent Test**: Run `re-derive --periodo <p>` twice; assert the `attachment_analyses` rows (ignoring volatile timestamps) are identical after both runs. Assert no R2 `get_object` call is made during either run.

### Edge Cases

- **Attachment with no stored transcription / only error records**: an attachment whose stored analysis records carry no parseable `response` (only `parse_error` rows, or no records at all) is left exactly as-is — re-derive cannot reconstruct a transcription that was never stored, and must not overwrite the existing analysis with an empty roll-up. (Same safety guard as the staging-driven apply.)
- **Legacy flat record (no `doc_type`)**: a stored response that is a legacy flat reconciliation record (pre-typed) is passed through the mappers unchanged (the mappers are idempotent on flat records), so re-deriving a legacy-classified attachment reproduces its prior roll-up. No special handling needed.
- **Shared-NF group**: when one attachment in a shared-NF group is in scope (by `--attachment-id`), the whole group is rebuilt together (the representative's transcription fans out to siblings and the group amount reconciliation runs), preserving the existing grouping semantics. Restoring the stored transcription as the group's input reproduces the same grouping the original apply produced.
- **Period in scope but no classified attachments**: a period with nothing classified yet produces no re-derive work and is skipped (no error).
- **`--attachment-id` for an unknown/unclassified id**: an id with no stored transcription contributes no work (skipped), consistent with the no-transcription edge case.
- **Mixed-scope conflict**: when both `--periodo` and `--attachment-id` are given, the attachment-id scope is applied within the named period(s) (intersection), matching the existing scoping convention of other commands.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST provide a `re-derive` CLI subcommand under `python -m analysis`.
- **FR-002**: `re-derive` MUST run the deterministic per-type mappers (EXTRACT-003) over the **stored** typed transcriptions (persisted in `attachment_analysis_records.response`) to rebuild the authoritative `attachment_analyses` roll-ups (and their flattened `attachment_analysis_records`).
- **FR-003**: `re-derive` MUST perform **zero** vision calls and **zero** page-image reads (no R2 `get_object`, no local image materialization). The transcription is read from the database only.
- **FR-004**: After rebuilding the roll-ups, `re-derive` MUST rebuild the global documents entity (equivalent to `build-documents`) and refresh alerts (equivalent to `analyze`) for the affected period(s), so the corrected reconciliation fields propagate to documents and findings.
- **FR-005**: `re-derive` MUST support scoping by period (`--periodo <YYYY-MM> …`) and by attachment id (`--attachment-id <id> …`), and MUST support a **global** run (no scope flags) that processes every already-classified attachment across all periods.
- **FR-006**: When scoped by attachment id, `re-derive` MUST rebuild each in-scope attachment together with its full shared-NF group (representative + siblings), so group amount reconciliation and sibling fan-out remain correct.
- **FR-007**: `re-derive` MUST be **idempotent**: running it repeatedly with no intervening mapper change produces identical database state (modulo volatile timestamps), reproducing each attachment's prior roll-up byte-for-byte when the mappers are unchanged.
- **FR-008**: `re-derive` MUST NOT overwrite an existing good `attachment_analyses` with an empty/error roll-up: an attachment whose stored transcription cannot be reconstructed (no parseable stored `response` on any page) MUST be left untouched.
- **FR-009**: `re-derive` MUST honor `--remote` (operate on the production D1/R2) and default to local; the flag MUST be threaded through every sub-step (roll-up rebuild, documents rebuild, alerts refresh).
- **FR-010**: `re-derive` MUST NOT write the scraper-owned mirror tables (`entries`, `attachments`, `accountability_reports`); it writes only analysis-owned tables (`attachment_analyses`, `attachment_analysis_records`, `attachment_state`, the `page_classifications` staging it manages internally, `documents`, `document_entries`, `alerts`), consistent with the mirror-table invariant (feature 026).
- **FR-011**: `re-derive` MUST print a concise, machine-parseable summary of what it did (count of attachments re-derived, count skipped for lack of a stored transcription, periods affected) to stdout; progress/banner text goes to the log (stderr).
- **FR-012**: When no in-scope attachment has a stored transcription, `re-derive` MUST complete without error and report that nothing was re-derived.

### Key Entities *(include if feature involves data)*

- **Stored transcription**: the per-page `response` JSON persisted in `attachment_analysis_records` — either a typed transcription (carries `doc_type`/`schema_version`, EXTRACT-001/004) or a legacy flat reconciliation record. This is the **input** re-derive reads; it is never modified by re-derive.
- **`attachment_analyses` roll-up**: the authoritative per-attachment analysis re-derive rebuilds (the same target `apply-extractions` writes).
- **Documents entity / alerts**: downstream derived tables refreshed after the roll-up rebuild (via the existing `build-documents` / `analyze` logic).

## Success Criteria *(mandatory)*

- **SC-001**: After a deterministic mapper fix, a single `re-derive` run corrects the reconciliation fields of **all** affected documents (across the chosen scope) with **zero** vision calls and **zero** page-image reads. *(Issue acceptance.)*
- **SC-002**: `re-derive` is idempotent: two consecutive runs with no mapper change leave the `attachment_analyses` rows identical (ignoring timestamps). *(Issue acceptance.)*
- **SC-003**: A scoped run (`--periodo` and/or `--attachment-id`) changes only the in-scope attachments' analyses and their downstream documents/alerts; out-of-scope data is byte-identical before and after.
- **SC-004**: An attachment with no parseable stored transcription is left untouched by re-derive (its existing analysis is not replaced with an empty roll-up).
- **SC-005**: `re-derive` writes no rows to the mirror tables (`entries`, `attachments`, `accountability_reports`) — verifiable by diffing those tables before/after a run.

## Assumptions

- **Source of stored transcriptions is `attachment_analysis_records.response`.** The `page_classifications` staging table is pruned after a successful apply (feature 035), so it is NOT a reliable steady-state source; the durable copy of each page's transcription lives in `attachment_analysis_records.response` (written verbatim at roll-up time, EXTRACT-004 / feature 055). Re-derive reads from there. This mirrors exactly how the corrections module reconstructs prior staging (`_snapshot_staging`) for its deterministic restore.
- **Implementation reuses the staging-driven apply.** Re-derive reconstructs each in-scope attachment's stored transcription into `page_classifications` staging rows (keyed `(attachment_id, page_label)`), clears its classified stamp, then runs the existing feature-050 staging-driven `apply_extractions` (which rolls up only groups whose representative has staging rows) → `run_analysis` (which itself rebuilds the global documents entity before writing alerts). This guarantees byte-for-byte consistency with the normal apply path and inherits its safety guard (no empty overwrite) and its atomic writebacks (feature 024), rather than inventing a parallel roll-up path. This is the same propagation primitive `corrections._propagate` already uses.
- **`run_analysis` covers FR-004's documents + alerts.** `run_analysis` calls `build_documents` and refreshes alerts atomically per period, so a single `run_analysis` over the affected periods satisfies the "build-documents then analyze" requirement; no separate `build-documents` invocation is needed in the common path.
- **Group reconstruction.** Reconstructing the stored transcription for a representative attachment and re-applying reproduces the same shared-NF grouping the original apply produced (grouping keys off `attachments.content_hash`, unchanged by re-derive). For attachment-id scope, the representative of each in-scope attachment's group is enrolled so the whole group rebuilds.
- **Idempotency source.** `attachment_analyses` is a pure function of the stored transcription + the mappers; with the mappers unchanged, re-deriving the same stored transcription reproduces the same roll-up. The only changes between two no-op runs are `analyzed_at`/`recorded_at` timestamps, which are excluded from idempotency assertions.
- **Default target is local; `--remote` is explicit** (never an implicit prod write), matching every other analysis command.
- **No new database schema or migration.** Re-derive reads and writes existing tables only.
- **Scope intersection.** When both `--periodo` and `--attachment-id` are given, the result is the intersection (the named attachments, restricted to the named periods), consistent with the loader's period filtering.

## Dependencies

- Depends on #87 (EXTRACT-003 deterministic per-type mappers) — **closed**.
- Depends on #89 (EXTRACT-004 persist typed transcriptions + flat-row coexistence) — **closed**. This is what stores the typed transcription verbatim in `attachment_analysis_records.response`, the source re-derive reads.
- Reuses the feature-050 staging-driven `apply_extractions` and the feature-035 staging prune.

## Out of Scope

- Re-vision / re-transcription of any page (that is the `apply-extractions` / classify path, not re-derive).
- Any change to the mappers themselves (re-derive is the propagation mechanism; fixing a mapper is a separate code change).
- A UI surface (re-derive is an engineer/agent CLI operation).
- Selecting which documents to re-derive by document type or by finding kind (scope is period/attachment/global only; a type-scoped re-derive can be a follow-up if needed).
