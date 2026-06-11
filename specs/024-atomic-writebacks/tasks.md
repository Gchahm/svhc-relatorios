# Tasks: Atomic delete-then-insert writebacks (no partial-failure data loss)

**Feature**: 024-atomic-writebacks | **Spec**: [spec.md](./spec.md) | **Plan**: [plan.md](./plan.md)
**Issue**: #37 (BUG-006)

All paths are repo-root-relative. The change is Python-only (analysis CLI); the Next.js frontend is
unaffected (it only reads these tables). Tests use stdlib `unittest` (no new dependency).

## Phase 1: Setup

- [X] T001 Create the Python test package at `scripts/tests/__init__.py` (empty file) so
  `python -m unittest discover -s scripts/tests -t scripts` can import `common` and `analysis` as
  top-level packages.

## Phase 2: Foundational (blocking prerequisite for all user stories)

- [X] T002 Add `upsert_sql(data: dict[str, list[dict]]) -> str` to `scripts/common/d1.py`: return
  `build_sql(data)[0]` when there are rows, else `""` (no execution). Refactor `upsert_tables` to
  `sql = upsert_sql(data); if sql: execute_sql(sql, target=target)` and still return the
  `build_sql(data)[1]` counts — executed SQL and return value byte-identical to today. (Contract C1.)
- [X] T003 [P] Add `scripts/tests/test_d1_upsert_sql.py`: assert `upsert_sql({"alerts": [row]})`
  equals `build_sql({"alerts": [row]})[0]`, that `upsert_sql({})` and `upsert_sql({"alerts": []})`
  return `""`, and (monkeypatching `d1.execute_sql`) that `upsert_tables` submits exactly that
  string and returns the expected counts. (Contract C1.)

## Phase 3: User Story 1 — Alerts survive a transient writeback failure (P1)

**Goal**: Each alerts writeback (per-period + global overpayment) clears + reinserts in one atomic
batch, so a partial failure never leaves a scope falsely empty.

**Independent test**: Run `test_alert_writeback_atomic.py` — one batch per scope; DELETE-only when
the new set is empty; a simulated `execute_sql` failure raises and prior alerts are untouched;
resolution grafting still runs before the batch.

- [X] T004 [US1] In `scripts/analysis/__init__.py:run_analysis`, replace the per-period
  `execute_sql(DELETE)` + separate `upsert_tables({"alerts": rows})` (lines ~108-111) with a single
  combined batch: build `sql = f"DELETE FROM alerts WHERE {where};\n" + d1.upsert_sql({"alerts":
  rows})` and call `d1.execute_sql(sql, target=target)` once. Keep `_read_existing_resolution` +
  `_graft_resolution` before building the batch (FR-007). When `rows` is empty, the batch is just the
  DELETE (FR-005). Preserve the existing per-period log line. (Contract C3.)
- [X] T005 [US1] In `scripts/analysis/__init__.py:run_analysis`, replace the global overpayment
  `execute_sql(DELETE … type='document_overpayment')` + separate `upsert_tables` (lines ~121-123)
  with a single combined batch the same way: `sql = "DELETE FROM alerts WHERE type =
  'document_overpayment';\n" + d1.upsert_sql({"alerts": overpayment_rows})` then one
  `d1.execute_sql`. Keep the `_graft_resolution(overpayment_rows, overpayment_prior)` before it.
  Preserve the existing log line. (Contract C4.)
- [X] T006 [P] [US1] Add `scripts/tests/test_alert_writeback_atomic.py`: monkeypatch
  `analysis.d1.execute_sql` to record submitted SQL (and `analysis.d1.query` to return prior rows for
  the resolution read), drive `run_analysis` with a tiny fake periods/checks setup (or call the
  writeback through `run_analysis` with stubbed `load_all_periods`/`run_all_checks`/
  `check_document_overpayment`/`build_documents`/`materialize_period_images`). Assert: (a) exactly one
  `execute_sql` per period scope and one for overpayment; (b) each captured SQL contains both the
  `DELETE FROM alerts WHERE …` and the `INSERT OR REPLACE … "alerts"` when rows exist; (c) DELETE-only
  when rows empty; (d) a side-effect that raises on `execute_sql` propagates and records no second
  call for that scope; (e) grafted `resolved`/`notes` still appear in the INSERT SQL (FR-007).

## Phase 4: User Story 2 — A failed attachment analysis re-runs automatically (P1)

**Goal**: The attachment-analysis writeback folds delete + insert + `classified_at` stamp into one
atomic batch, so a failed insert leaves the attachment pending (self-healing), never stamped-empty.

**Independent test**: Run `test_attachment_writeback_atomic.py` — one batch containing the two
DELETEs, the analysis INSERT, and the `classified_at` UPDATE; a simulated failure raises and the
UPDATE is never committed alone with the DELETE.

- [X] T007 [US2] In `scripts/analysis/attachments.py:_merge_and_write`, build one combined batch:
  the two `DELETE` statements (records + analysis) + `d1.upsert_sql({"attachment_analyses":
  [result.to_dict()]})` + the `UPDATE attachments SET classified_at = {now_ms()} WHERE id = '{did}'`
  — submitted via a single `d1.execute_sql(sql, target=target)`. Remove the now-redundant separate
  `d1.upsert_tables(...)` call and ensure the stamp is no longer in a delete-only batch. Update the
  function docstring to state the writeback is atomic and the stamp commits with the insert.
  (Contract C2; FR-001, FR-002.)
- [X] T008 [P] [US2] Add `scripts/tests/test_attachment_writeback_atomic.py`: monkeypatch
  `analysis.attachments.d1.execute_sql` to capture SQL, construct a minimal `AttachmentAnalysisResult`
  (valid id/records), call `_merge_and_write`, and assert: (a) exactly one `execute_sql`; (b) the SQL
  contains both DELETEs, the `INSERT OR REPLACE … "attachment_analyses"`, and `UPDATE attachments SET
  classified_at`; (c) no `upsert_tables` second call; (d) when `execute_sql` is made to raise, the
  exception propagates (FR-004) and there was no separate batch that committed the stamp/delete alone
  (FR-002).

## Phase 5: User Story 3 — Loud, actionable error on partial failure (P2)

**Goal**: A writeback failure surfaces loudly (propagates) rather than completing silently.

**Independent test**: The failure assertions in T006/T008 confirm propagation; add a focused check
that the raised error is not swallowed by the writeback functions.

- [X] T009 [US3] Verify (and adjust only if needed) that `run_analysis` and `_merge_and_write` do
  NOT wrap the `execute_sql` calls in a swallowing `try/except` — failures must propagate
  (`subprocess.CalledProcessError` from `d1.execute_sql`). If any scope-identifying context would
  help operators, attach it by letting the exception propagate after the existing per-scope log line;
  do not add a bare `except`. (FR-004.) Covered behaviorally by the failure cases in T006 + T008.

## Phase 6: Polish & Cross-Cutting

- [~] T010 Run `python -m unittest discover -s scripts/tests -t scripts` and `pnpm lint`/`pnpm
  format`. NOTE: the sandbox in this environment denies executing Python and the speckit scripts, so
  the suite was authored and verified by inspection here; it is runnable as documented (stdlib only,
  no new deps) and the CI/reviewer can execute it. No TS/ESLint-relevant files changed.
- [X] T011 [P] Update `CLAUDE.md` (Important Patterns) to note that the attachment-analysis and
  alert writebacks are **atomic single-batch** (delete + insert [+ classified_at stamp] in one
  `execute_sql`), and document the new `common/d1.py:upsert_sql` helper. Keep it to ~2-3 sentences
  threaded into the existing analysis/writeback patterns.

## Dependencies & Execution Order

- **Phase 1 (T001)** → **Phase 2 (T002, T003)** must complete first — `upsert_sql` is the shared
  primitive both stories use.
- **US1 (T004-T006)** and **US2 (T007-T008)** are independent of each other (different files:
  `__init__.py` vs `attachments.py`) and can proceed in parallel once T002 lands.
- **US3 (T009)** is a verification over the files edited in US1/US2; do after T004/T007.
- **Polish (T010-T011)** last.

## Parallel Opportunities

- T003, T006, T008, T011 are `[P]` — separate new test files / docs, no shared edits.
- US1 and US2 implementation (T004/T005 vs T007) touch different modules → parallelizable.

## Implementation Strategy

MVP = Phase 1 + Phase 2 + **either** US1 or US2 (each independently removes a partial-failure data
loss). Ship both P1 stories together since they share the foundational helper and are small.
Suggested order: T001 → T002 → T003 → (T004,T005,T007 in any order) → T006,T008 → T009 → T010,T011.
