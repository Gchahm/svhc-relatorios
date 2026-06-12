# Tasks: Prune consumed and stale `page_classifications` staging rows

**Feature**: `035-prune-staging-rows` | **Spec**: [spec.md](./spec.md) | **Plan**: [plan.md](./plan.md)

Tests requested (atomicity + scoping are correctness-critical; spec SC-001..SC-004). All Python,
stdlib `unittest`, run with `python -m unittest discover -s scripts/tests -t scripts`.

## Phase 1: Setup

- [x] T001 Confirm the existing atomic-batch seams are intact before editing: read `_merge_and_write` in `scripts/analysis/attachments.py` and `mark_pending` in `scripts/analysis/extractions.py` to confirm each builds a single `execute_sql` string (no behavior change in this task).

## Phase 2: Foundational (blocking prerequisite for both stories)

- [x] T002 Add the pure helper `_prune_page_classifications_sql(attachment_ids: list[str]) -> str` to `scripts/analysis/page_classifications.py`: returns `""` for an empty list, else `DELETE FROM page_classifications WHERE attachment_id IN ('a','b',…);` with each id single-quote-escaped (`'` → `''`) and a trailing `;`. No I/O. Docstring references the `upsert_sql` / `documents._prune_sql` "return SQL, caller batches it" convention.
- [x] T003 [P] Add `scripts/tests/test_prune_staging.py` with unit tests for `_prune_page_classifications_sql`: empty → `""`; single id; multiple ids (comma-joined, no spaces matching the codebase style); id containing a single quote is escaped; output ends with `;`.

## Phase 3: User Story 1 — Consumed staging rows removed after apply (P1)

**Goal**: After an attachment's authoritative `attachment_analyses` write lands, its staging rows are deleted, atomically with the write.

**Independent test**: Record staging rows for an attachment, run apply, confirm staging rows gone and analysis present; a failed write leaves staging rows intact.

- [x] T004 [US1] In `scripts/analysis/attachments.py` `_merge_and_write`, append `_prune_page_classifications_sql([result.attachment_id])` to the SQL string AFTER the `attachment_analyses` INSERT + `attachment_state` upsert, so it lands in the same `execute_sql` batch (import the helper from `.page_classifications`). Update the docstring to note the staging-row consume + its atomicity guarantee (commits with the insert; a failed write leaves staging rows + leaves the attachment pending).
- [x] T005 [P] [US1] In `scripts/tests/test_prune_staging.py`, add a test asserting `_merge_and_write` composes the staging-prune DELETE into the SAME `execute_sql` call as the analysis INSERT (monkeypatch `d1.execute_sql` to capture the SQL; assert it contains both the `INSERT ... attachment_analyses` and `DELETE FROM page_classifications WHERE attachment_id IN ('<id>')`, and that only ONE `execute_sql` call was made — proving atomicity / no separate round trip). Assert the DELETE is scoped to exactly the attachment id (FR-006).

## Phase 4: User Story 2 — Re-queue clears staging rows (P2)

**Goal**: `mark-pending` deletes a re-queued attachment's staging rows (attachment-id and entry-id scope) in the same batch that clears `attachment_state.classified_at`; no-op when no ids.

**Independent test**: Record staging rows, run `mark-pending` for the attachment, confirm rows gone; no ids → nothing happens, returns 0.

- [x] T006 [US2] In `scripts/analysis/extractions.py` `mark_pending`, when at least one id is given, append a `DELETE FROM page_classifications WHERE <scope>` to the same `execute_sql` as the `UPDATE attachment_state …`, where `<scope>` mirrors the UPDATE clauses (attachment ids literal `attachment_id IN (…)`; entry ids via the existing read-only subquery `attachment_id IN (SELECT id FROM attachments WHERE entry_id IN (…))`). Keep the no-ids no-op + return-value behavior unchanged. Update the docstring to note the staging-row clear.
- [x] T007 [P] [US2] In `scripts/tests/test_prune_staging.py`, add tests for `mark_pending` (monkeypatch `d1.execute_sql`): (a) attachment-id scope → single `execute_sql` containing both the `UPDATE attachment_state SET classified_at = NULL` and `DELETE FROM page_classifications` scoped to that id; (b) entry-id scope → the DELETE uses the `SELECT id FROM attachments WHERE entry_id IN (…)` subquery; (c) no ids → `execute_sql` not called and return value is 0 (FR-004).

## Phase 5: Polish & Cross-Cutting

- [x] T008 Run the full Python test suite: `python -m unittest discover -s scripts/tests -t scripts` — all new + pre-existing tests pass.
- [x] T009 Update `CLAUDE.md` "Important Patterns" with a one-paragraph note on the staging-table pruning (feature 035 / issue #42): apply consumes an attachment's `page_classifications` rows in `_merge_and_write`'s atomic batch; `mark-pending` clears them on re-queue; no schema change, no mirror write, the portal-deletion cascade still covers removed attachments.
- [x] T010 Verify against local D1 per `quickstart.md` (mark-pending clears an attachment's staging rows; staging count drops); record the result for the PR body.

## Dependencies

- T002 (helper) blocks T004 and T006 (both callers use it). T003 can run alongside T002.
- US1 (T004/T005) and US2 (T006/T007) are independent once T002 lands and can be done in either order.
- T008 after all implementation; T009/T010 last.

## Parallel opportunities

- T003 [P] alongside T002.
- T005 [P] and T007 [P] are independent test additions (same file — coordinate edits, but logically independent of each other).

## MVP

User Story 1 (T002, T004 + tests) is the MVP — it stops the unbounded growth on the primary path. User Story 2 adds the re-queue-clean guarantee.
