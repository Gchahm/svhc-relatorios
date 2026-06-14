# Tasks: Data-correction audit trail + reversibility (autonomous-correction safety net)

**Feature**: 054-correction-audit-trail | **Input**: spec.md, plan.md, research.md, data-model.md, contracts/corrections-cli.md

Tests ARE requested (US1–US3 each define an Independent Test; spec SC-001..005). Unit tests live in
`scripts/tests/`, integration in `scripts/integration_tests/`.

## Phase 1: Setup

- [x] T001 Add the `data_corrections` table to `src/db/fiscal.schema.ts` (Drizzle) per data-model.md: columns `id, batch_id, attachment_id (refs attachments.id), period, page_label, field, from_value, to_value, evidence, agent, target_finding_key, status, detail, from_staging, created_at, reverted_at, reverted_by` + indexes on `attachment_id`, `status`, `period`. Place it near `pageClassifications`/`alerts` with a section comment marking it analysis-owned.
- [x] T002 Generate + apply the migration: run `node_modules/.bin/drizzle-kit generate` (per memory `db-generate-pnpm-workaround`, call the binary directly) to create `drizzle/0014_*.sql`, then `pnpm db:migrate:dev`. Verify the table exists locally with a `wrangler d1` query. Commit the generated SQL + `drizzle/meta` changes.

## Phase 2: Foundational (blocking prerequisites for all stories)

- [x] T003 Create `scripts/analysis/corrections.py` skeleton (module docstring describing the store + apply/list/undo; stdlib + `common.d1` + `common.det_id`/`now_ms` only). Define the `TABLE = "data_corrections"`, the `STATUS_*` constants (`applied`/`rolled-back`/`flagged`/`reverted`), and `CORRECTION_AGENT_DEFAULT`/`UNDO_ACTOR_DEFAULT` sentinels.
- [x] T004 [P] In `scripts/analysis/corrections.py` implement the pure id builders: `batch_id(attachment_id, target_finding_key, corrected_pages) -> str` (`det_id("data_correction_batch", …, canonical(corrected_pages))`) and `correction_id(batch_id, page_label, field) -> str` (`det_id("data_correction", …)`), with a deterministic `_canonical(corrected_pages)` JSON serialization (sorted keys) so identical inputs ⇒ identical ids (FR-012).
- [x] T005 [P] In `scripts/analysis/corrections.py` implement the pure `field_diff(current_fields: dict | None, corrected_fields: dict) -> list[dict]`: returns one `{field, from, to}` per field whose value differs (JSON-comparable), skipping unchanged fields. Empty list ⇒ no-op (FR-009). `current_fields=None` (no prior staging for the page) means every corrected field is a change from null.
- [x] T006 [P] In `scripts/analysis/corrections.py` implement the pure `verify_after(before_keys: set[str], after_keys: set[str], target_finding_key: str) -> tuple[bool, str]`: `(False, "unverifiable: …")` if target not in before (caller treats as fail-closed, FR-010); else PASS iff target NOT in after AND no key in `after_keys - before_keys`; returns a descriptive reason on fail (FR-004).
- [x] T007 [P] In `scripts/analysis/corrections.py` implement the pure `can_undo(status: str) -> bool` (True only for `applied`) and a `correction_row(...)` builder assembling a `data_corrections` row dict (JSON-encoding `from_value`/`to_value`/`from_staging`) for upsert via `d1.upsert_tables`.

## Phase 3: User Story 1 — autonomous correction is logged + verify-after gated (Priority: P1) 🎯 MVP

**Goal**: `apply_correction(...)` records each field change and only lets the data change stand when
verify-after passes; on failure it restores the pre-correction state and records the outcome.

**Independent Test**: drive `apply_correction` against seeded local data for a known misread
attachment — assert audit row written with all fields, data changed on pass, data restored + record
`rolled-back` on an injected verify failure.

- [x] T008 [US1] In `scripts/analysis/corrections.py` implement `_affected_scope(attachment_id, target, cache_dir)` → the attachment + its shared-NF sibling attachment ids (reuse `nf_groups.group_attachments` / `load_all_periods` so the scope matches the apply fan-out), and `_findings_for(attachment_ids, target, cache_dir)` → the set of `mismatch_key`s from `summarize_mismatches(attachment_ids=…)` (reuse `verdicts.mismatch_key`).
- [x] T009 [US1] In `scripts/analysis/corrections.py` implement `_snapshot_staging(attachment_id, target)` (read the attachment's current `page_classifications` rows) and `_current_page_fields(snapshot, page_label)` (extract the prior fields object for a page, or None), so `field_diff` has its `current` side.
- [x] T010 [US1] In `scripts/analysis/corrections.py` implement `_propagate(attachment_id, period, target, cache_dir)`: `mark_pending(attachment_ids=[id])` → `apply_extractions(periods_filter=[period])` → `build_documents()` → `run_analysis(periods_filter=[period])`. (Reuses the staging-driven apply so only this attachment's group is rolled up.)
- [x] T011 [US1] In `scripts/analysis/corrections.py` implement `_restore_staging(attachment_id, snapshot, target)`: one atomic `execute_sql` batch = `DELETE FROM page_classifications WHERE attachment_id=…` + `upsert_sql({page_classifications: snapshot})` (feature 024 idiom); returns True on success, False (caught) on failure for the `flagged` path.
- [x] T012 [US1] In `scripts/analysis/corrections.py` implement `apply_correction(attachment_id, target_finding_key, corrected_pages, *, evidence=None, agent=CORRECTION_AGENT_DEFAULT, target="local", cache_dir=…) -> dict` wiring T008–T011 per contract: validate each corrected page (`validate_page_fields`), compute BEFORE findings (fail-closed if target absent → `unverifiable`, no change), snapshot + diff (empty ⇒ `no-op`, no row), write corrected staging (`record_classification`), propagate, compute AFTER findings, `verify_after`; on PASS write rows `status=applied`; on FAIL restore → rows `rolled-back` (or `flagged` if restore failed); return the contract result dict. Resolve a default `evidence` from the target finding's `page_refs` when not supplied.
- [x] T013 [US1] Wire the `apply-correction` subcommand into `scripts/analysis/__main__.py` (args per contract; parse `--pages` JSON from arg or stdin `-`; map `--remote`→target; print the result dict as JSON; exit non-zero on `rolled-back`/`flagged`/`unverifiable`).
- [x] T014 [P] [US1] Unit tests in `scripts/tests/test_corrections.py` for the pure seams: `field_diff` (changed/unchanged/null-from), `verify_after` (pass, target-not-cleared, new-finding, unverifiable), `can_undo`, id-builder determinism/idempotence (FR-012), `correction_row` JSON encoding.
- [x] T015 [US1] Integration test in `scripts/integration_tests/test_corrections_d1.py` (real local Miniflare D1, synthetic period via the harness): apply a correction whose verify passes → assert data changed + an `applied` row with all required fields; inject a verify failure (a correction that does NOT clear the target, or that introduces a new finding) → assert the pre-correction `attachment_analyses` is byte-restored (SC-002) and a `rolled-back` row exists; assert no-op + unverifiable paths write no row.

**Checkpoint**: US1 independently delivers the recording + verify-after safety net (MVP).

## Phase 4: User Story 2 — human review + undo (Priority: P1)

**Goal**: a human can list every correction and undo any applied one (restore + re-derive + record).

**Independent Test**: apply a correction, list it (all fields present), undo it, assert the
pre-correction value is restored, the original finding reappears, and a `reverted` record exists.

- [x] T016 [US2] In `scripts/analysis/corrections.py` implement `list_corrections(*, attachment_ids=None, period=None, status=None, target="local") -> list[dict]`: a scoped `SELECT * FROM data_corrections` (WHERE clauses for the given filters, single-quote-escaped), decoding `from_value`/`to_value`, ordered `created_at DESC, id` (FR-006).
- [x] T017 [US2] In `scripts/analysis/corrections.py` implement `undo_correction(correction_or_batch_id, *, actor=UNDO_ACTOR_DEFAULT, target="local", cache_dir=…) -> dict`: load the batch (accept a row id or a batch_id), reject if any row's status ≠ `applied` (`can_undo`, FR-008, no change), else `_restore_staging` + `_propagate`, then update the batch rows `status=reverted, reverted_at, reverted_by` (one `execute_sql`); return the contract result.
- [x] T018 [US2] Wire `list-corrections` + `undo-correction` subcommands into `scripts/analysis/__main__.py` per contract (filters; `--id`; `--actor`; JSON stdout; exit non-zero on `rejected`).
- [x] T019 [P] [US2] Unit tests in `scripts/tests/test_corrections.py`: `list_corrections` WHERE-clause/ordering builder (scoped vs unscoped), `undo_correction` status guard (rejects `rolled-back`/`flagged`/`reverted`).
- [x] T020 [US2] Integration test in `scripts/integration_tests/test_corrections_d1.py`: after an applied correction, `list_corrections` returns it with every field; `undo_correction` restores the pre-correction value (SC-003), the original finding reappears in `summarize_mismatches`, and the record is `reverted` with `reverted_at`/`reverted_by`; a second undo of the same batch is rejected (FR-008).

## Phase 5: User Story 3 — durability + independence from the code-fix loop (Priority: P2)

**Goal**: the trail survives an ephemeral-cache wipe and shares nothing with `verdicts.json`.

**Independent Test**: apply a correction, delete `.cache/analysis/`, assert the record is still
listable + undoable; assert the verdicts store and the corrections store do not contain each other.

- [x] T021 [US3] Integration test in `scripts/integration_tests/test_corrections_d1.py`: apply a correction, delete the ephemeral cache dir, then `list_corrections` still returns it and `undo_correction` still works (SC-004) — proves the store is in D1, not the cache.
- [x] T022 [P] [US3] Assert independence in `scripts/tests/test_corrections.py`: the `data_corrections` row shape shares no schema with `verdicts.py` records (no `mismatch_key`/`verdict`/`fix` fields leaking) and `corrections.py` does not read/write any `<period>.verdicts.json` (US3-AC2) — a structural assertion over the module's public surface.

## Phase 6: Polish & Cross-Cutting

- [x] T023 [P] Update `CLAUDE.md` with a concise "Data-correction audit trail (feature 054 / TRIAGE-003)" bullet: the analysis-owned `data_corrections` store, the apply-correction verify-after gate + rollback/flag, list/undo, the staging-snapshot restore, and that it reuses the staging-driven apply (feature 050) — keep consistent with the existing CLAUDE.md style and reference the spec.
- [x] T024 [P] Update `scripts/.coveragerc` only if needed (corrections.py is in `analysis`, already in `[run] source`); confirm `pnpm test:py:cov` still passes `fail_under`. Run `pnpm test:py` + `pnpm test:py:integration` + `pnpm lint` + `pnpm format` (and `prettier --check .` over markdown per memory `prettier-docs-ci-gate`) — fix any failures.
- [x] T025 Manual verification per quickstart.md against the seeded local period (`pnpm e2e:seed`): apply (pass), list, undo, and an injected rollback; confirm each prints the expected result JSON and the data state matches. Record the outcomes for the PR body.

## Dependencies

- Phase 1 (T001–T002, schema) blocks everything (no table → no store).
- Phase 2 (T003–T007, pure seams) blocks Phase 3+.
- US1 (Phase 3) is the MVP and blocks nothing else structurally, but US2/US3 reuse `apply_correction`
  + `_restore_staging` from US1, so US1 completes first.
- US2 (Phase 4) depends on US1's store + restore helpers.
- US3 (Phase 5) depends on US1 (apply) + US2 (list/undo) existing.
- Polish (Phase 6) last.

## Parallel execution examples

- After T003: T004, T005, T006, T007 are independent pure functions in the same file — author
  together (mark [P] but they touch one file, so land sequentially if editing serially).
- T014 (unit) parallels T013 (CLI wiring) once T012 exists. T019/T022 (unit) parallel their CLI/IT
  siblings.
- T023, T024 (docs/coverage) are independent of each other.

## Implementation strategy

MVP = Phase 1 + 2 + 3 (US1): a durable, verify-after-gated, logged correction. Ship/verify that
slice, then add US2 (review+undo) and US3 (durability assertions). Each user story is independently
testable per its Independent Test.
