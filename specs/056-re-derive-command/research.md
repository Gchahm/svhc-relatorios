# Phase 0 Research: Re-derive command

## R1 — Source of the stored transcription

**Decision**: Read each page's transcription from `attachment_analysis_records.response` (joined via the attachment's `attachment_analyses` row), NOT from the `page_classifications` staging table.

**Rationale**: Feature 035 prunes the `page_classifications` staging rows once `apply-extractions` rolls them up, so a steady-state classified attachment has **no** staging rows — but its frozen per-page transcription lives durably in `attachment_analysis_records.response` (written verbatim at roll-up time, EXTRACT-004 / feature 055). `corrections._snapshot_staging` already reads from exactly there for its deterministic restore, proving the source is correct and complete (research D3 in the corrections feature: restoring those records as staging and re-applying re-derives the prior `attachment_analyses` byte-for-byte).

**Alternatives considered**:
- *Read from `page_classifications`* — rejected: pruned after apply, so empty for most rows; would re-derive nothing.
- *Add a new durable transcription store* — rejected: the records table already is that store; no schema change is warranted (Constitution V).

## R2 — Roll-up mechanism: reuse the staging-driven apply vs a parallel path

**Decision**: Reconstruct staging rows from the stored records → clear the classified stamp → run the feature-050 staging-driven `apply_extractions` → `run_analysis`. This is the exact propagation primitive `corrections._propagate` uses.

**Rationale**:
- **Byte-for-byte consistency.** Using the same `apply_extractions` path means the re-derived roll-up is produced by the identical code (grouping, fan-out, group amount reconciliation, atomic writeback) as the normal classify path — so re-derive and apply can never drift, and idempotency under unchanged mappers is guaranteed (`attachment_analyses` is a pure function of the staged transcription + the mappers).
- **Inherits the safety guard (FR-008).** The staging-driven apply rolls up only groups whose representative has staging rows; an attachment with no parseable stored transcription contributes no staging rows, so it is never visited and never overwritten with an empty roll-up.
- **Inherits atomic writebacks (feature 024).** `_merge_and_write` and the alert writebacks are already one atomic batch each.

**Alternatives considered**:
- *A parallel in-memory roll-up that writes `attachment_analyses` directly* — rejected: duplicates `apply_extractions`'s grouping/fan-out/reconciliation logic, risks drift, and re-implements the safety guard. Constitution V (simplicity) favors reuse.

## R3 — Where the transcription→staging reconstruction lives (avoid duplication)

**Decision**: Factor the "stored `attachment_analysis_records.response` → `page_classifications`-shaped rows" reconstruction into a small shared, importable helper that both `corrections` and the new `re_derive` call. `corrections._snapshot_staging` becomes a thin wrapper over (or is replaced by) that helper.

**Rationale**: `re_derive` needs the identical reconstruction `corrections._snapshot_staging` does. Duplicating it would create two copies of a subtle SQL+decode routine that must stay in lock-step (the staging row id keyed on `(attachment_id, page_label)`, the JSON decode, the `parse_error` → `error` mapping). A single shared helper keeps them coherent. Placement: `page_classifications.py` already owns the staging row contract and id (`page_classification_id`), so a `staging_rows_from_records(rows)` (pure, takes already-queried record dicts) plus a `load_stored_records(attachment_id, target)` (the D1 read) sit naturally there; the pure transform is unit-testable without D1.

**Alternatives considered**:
- *Import the private `corrections._snapshot_staging` from `re_derive`* — rejected: cross-module dependency on a private name, and `_snapshot_staging` couples the D1 read + the transform; the pure transform should be separately testable.

## R4 — Scope resolution (period / attachment / global)

**Decision**: Resolve the in-scope attachment set as: load periods (`load_all_periods(target, periods_filter)`); the candidate attachments are those with a persisted `attachment_analyses` row (i.e. already classified) within the loaded periods; if `--attachment-id` is given, intersect with that set. Then, for shared-NF correctness (FR-006), expand each in-scope attachment to its full group's representative so the whole group re-derives via the staging-driven apply.

**Rationale**: The loader already filters by period and re-nests `attachment_analyses` with decoded `analysis_records`, so the candidate set and the stored transcription are available from one load. Intersecting `--attachment-id` within `--periodo` matches the spec's intersection decision and the loader's period filtering. Expanding to the group representative is required because the staging-driven apply selects groups by their representative's staging presence; staging only the rep (or any member whose staging we write) and clearing the stamps of the affected attachments ensures the group is rolled up and fanned out exactly as the original apply did.

**Note on grouping**: `select_work` / `group_attachments` group by `attachments.content_hash`. Re-derive does not change `content_hash` (mirror-owned), so grouping is identical to the original apply. Reconstructing the representative's stored transcription into staging and clearing the group members' stamps reproduces the same group roll-up.

**Alternatives considered**:
- *Re-derive only the exact attachment ids without group expansion* — rejected: the staging-driven apply is group-keyed; without enrolling the representative the group amount reconciliation would be wrong, and a sibling whose stamp was cleared but whose rep has no staging would be skipped (left pending), an undesirable side effect. Expanding to the whole group is correct and matches apply semantics.

## R5 — Documents + alerts refresh (FR-004)

**Decision**: One `run_analysis(target, periods_filter=affected_periods)` after the roll-up rebuild. `run_analysis` calls `build_documents` (global) and writes alerts atomically per period.

**Rationale**: `run_analysis` already sequences `build_documents` then the checks/alerts (`scripts/analysis/__init__.py`), so a single call satisfies "build-documents then analyze". `build_documents` is global and idempotent (prunes stale), so re-deriving any subset still yields a correct global documents entity. Scoping `run_analysis` to the affected periods refreshes only those periods' alerts (atomic delete+insert per `reference_period`), leaving out-of-scope periods' alerts untouched (SC-003).

**Alternatives considered**:
- *Call `build_documents` + `analyze` separately* — functionally equivalent but redundant; `run_analysis` is the existing one-shot. Reuse it (Constitution V).

## R6 — Idempotency and no-op handling

**Decision**: Idempotency follows from R2 (pure function of stored transcription + mappers). For the no-work case (no in-scope attachment has a parseable stored transcription), `re_derive` completes without error, writes nothing, and reports zero re-derived (FR-012). A clear-stamp + apply + run_analysis sequence on an empty staged set is a safe no-op (apply skips groups with no staging; run_analysis over the periods just re-writes the same alerts/documents idempotently — but to avoid needless churn, skip the apply/analyze entirely when nothing was staged).

**Rationale**: Avoiding the apply/analyze when nothing is staged keeps a no-scope-match run a true no-op and avoids re-writing unrelated alerts.

## R7 — Verification approach (Constitution III + project memory)

**Decision**: Verify against local Miniflare D1 with the existing synthetic seed (`pnpm e2e:seed` populates the `2099-01` synthetic period with classified attachments + analysis records), then run `python -m analysis re-derive --periodo 2099-01` and assert the analyses are reproduced and no mirror write occurred. Plus unit tests (pure staging reconstruction + scope resolution) and a real-D1 integration test (reproduce-analysis, idempotent, scoped, no-mirror-write).

**Rationale**: The repo's verification convention for the analysis pipeline is the Python `unittest` suites (pure + real-D1) — there is no UI surface for this feature, so the ui-reviewer is not applicable. The synthetic seed provides prod-like classified data with stored transcriptions to exercise re-derive end-to-end.
