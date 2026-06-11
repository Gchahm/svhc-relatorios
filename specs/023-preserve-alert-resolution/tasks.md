# Tasks: Preserve user-set alert resolution state across analysis re-runs

**Feature**: `023-preserve-alert-resolution` | **Spec**: [spec.md](./spec.md) | **Plan**: [plan.md](./plan.md)

This is a pipeline-only fix in `scripts/analysis/`. No schema change, no frontend change, no new
dependencies. Tests are OPTIONAL (no framework configured) — verification is manual per
`quickstart.md`.

## Phase 1: Setup

- [x] T001 Confirm working tree on branch `023-preserve-alert-resolution` and review the two
  writeback sites in `scripts/analysis/__init__.py` (per-period delete ~line 51; global
  `document_overpayment` delete ~line 62) plus the hardcoded reset in
  `scripts/analysis/models.py` (`Alert.to_dict`, lines 33-35).

## Phase 2: Foundational

- [x] T002 Add a resolution-preservation helper in `scripts/analysis/__init__.py` (or a small new
  module `scripts/analysis/alerts_io.py`) with two pure-ish functions:
  (a) `read_existing_resolution(where_sql: str, target) -> dict[str, dict]` — runs
  `SELECT id, resolved, resolved_at, notes FROM alerts WHERE <where_sql>` via `common.d1.query`,
  returning `{id: {"resolved", "resolved_at", "notes"}}` for rows where `resolved` is truthy OR
  `notes` is non-empty; and (b) `graft_resolution(rows: list[dict], existing: dict[str, dict]) ->
  None` — for each row whose `id` is in `existing`, overwrite `resolved`/`resolved_at`/`notes`.
  Keep the WHERE clause identical to the matching delete so scope can't drift (data-model.md
  "Scopes"). Stdlib only.

## Phase 3: User Story 1 — Resolution survives a re-analysis (P1)

**Goal**: A re-emitted alert keeps `resolved`/`resolved_at`/`notes`.
**Independent test**: quickstart.md Test 1 (per-period) + Test 2 (global overpayment).

- [x] T003 [US1] In `scripts/analysis/__init__.py` `run_analysis`, for the **per-period**
  writeback: BEFORE `DELETE FROM alerts WHERE reference_period = '<p>'`, call
  `read_existing_resolution("reference_period = '<p>'", target)`; after building `rows`, call
  `graft_resolution(rows, existing)`; then delete + `upsert_tables` as today. Use the same escaped
  period string for the read and the delete.
- [x] T004 [US1] In the same function, for the **global `document_overpayment`** writeback: BEFORE
  `DELETE FROM alerts WHERE type = 'document_overpayment'`, call
  `read_existing_resolution("type = 'document_overpayment'", target)`; graft onto the overpayment
  rows before insert.
- [x] T005 [US1] In `scripts/analysis/models.py`, keep `Alert.to_dict()` emitting the unresolved
  default (a freshly-detected alert IS unresolved) but add a comment that the writeback merge in
  `run_analysis` is the authority for re-emitted rows (FR-004) — so the hardcoded values are the
  documented default for new alerts, not a silent reset.

## Phase 4: User Story 2 — Stale findings still clear (P2)

**Goal**: Findings that no longer fire disappear (including their resolution state).
**Independent test**: quickstart.md Test 3.

- [x] T006 [US2] Verify by inspection that grafting only touches rows present in BOTH the existing
  map and the new `rows` list — ids absent from `rows` are not re-inserted, so the delete drops
  them. No code beyond T003/T004 should be needed; if `graft_resolution` ever inserts missing ids,
  remove that behavior. (Guarantee 2 in contracts/alert-writeback.md.)

## Phase 5: Polish & Cross-Cutting

- [x] T007 Manually verify guarantees 1–4 following `quickstart.md` (per-period preserve, global
  preserve, obsolete-clear, idempotency) against local D1.
- [x] T008 Run `pnpm lint` and `pnpm format`; confirm clean. (No Python formatter is configured;
  match surrounding style in `scripts/analysis/`.)
- [x] T009 Commit on the feature branch with a message referencing issue #34 (e.g.
  `fix(023): preserve user alert resolution/notes across analysis re-runs (#34)`).

## Dependencies

```
T001 → T002 → { T003, T004 } → T005 → T006 → T007 → T008 → T009
```

- T002 (shared helper) blocks both writeback edits (T003, T004).
- T003 and T004 touch the same file in nearby regions → do them sequentially (not [P]).
- T006 is a verification gate over T003/T004; T007–T009 are final polish.

## Parallel Opportunities

Minimal — the change is concentrated in one file. T003 and T004 edit `scripts/analysis/__init__.py`
and must not be parallelized. No `[P]` tasks.

## Implementation Strategy

MVP = Phase 1–3 (US1): the preservation merge wired into both writeback paths. US2 is satisfied by
the same delete-then-insert structure and only needs verification (T006). Ship after T007 passes.
