# Tasks: Trim feature-054 correction integration tests

**Feature**: `060-trim-correction-integration-tests`
**Plan**: [plan.md](./plan.md) | **Spec**: [spec.md](./spec.md)

All work is confined to ONE file: `scripts/integration_tests/test_corrections_d1.py`. Because the
three user stories all manifest as coordinated edits to the same module, they cannot be parallelized
(no `[P]` markers) — they share one file. The phases below still group the edits by the story they
satisfy so each remains independently verifiable.

## Phase 1: Setup

- [x] T001 Confirm the branch `060-trim-correction-integration-tests` is checked out and
      `scripts/integration_tests/test_corrections_d1.py` is the unmodified #99 baseline (7 tests,
      `setUp` calling `h.restore()`, inline `import shutil` in the durability test).

## Phase 2: Foundational

- [x] T002 Add `import shutil` to the module-level import block in
      `scripts/integration_tests/test_corrections_d1.py` (top of file, with the other stdlib
      imports), satisfying FR-006. (The inline `import shutil` inside the to-be-deleted durability
      test is removed in Phase 3 when that test is deleted.)

## Phase 3: User Story 3 — clean shared-process baseline (Priority: P2, but a prerequisite edit)

**Goal**: `setUp` stops re-seeding globally per test; `tearDownClass` keeps the baseline reset.
**Independent test**: `setUp` has no `h.restore()`; `tearDownClass` still calls it.

- [x] T003 [US3] In `setUp` of `TestCorrectionsD1`
      (`scripts/integration_tests/test_corrections_d1.py`), remove the `h.restore()` line; keep the
      rest (resolve E3 attachment/entry/period, `tempfile.mkdtemp()`, delete this attachment's
      `data_corrections` rows). Update the comment to explain why no per-test restore is needed
      (E3-scoped, alerts rewritten atomically, baseline reset stays in `tearDownClass`). Leave
      `tearDownClass` unchanged (FR-002, FR-003).

## Phase 4: User Story 1 + User Story 2 — faster job, no coverage loss (Priority: P1)

**Goal**: Collapse the four `applied`-path tests into one lifecycle test preserving every assertion;
keep the three distinct-path tests unchanged.
**Independent test**: exactly 4 test methods; the lifecycle test asserts the full merged set.

- [x] T004 [US1] Delete the four redundant tests from
      `scripts/integration_tests/test_corrections_d1.py`: `test_apply_pass_records_and_changes`,
      `test_undo_restores_and_records`, `test_second_undo_rejected`,
      `test_record_survives_cache_wipe` (the last carries the inline `import shutil`, now removed
      with it).
- [x] T005 [US2] Add `test_applied_lifecycle_record_list_durability_undo` to `TestCorrectionsD1`
      (verbatim from the issue): one `_stage_and_propagate(800)` + one `apply_correction(→250)` +
      one `undo_correction`, asserting applied result, data change (250), finding cleared, full
      audit-row fields (`from_value`/`to_value`/`evidence`/`agent`/`page_label`/`target_finding_key`/
      `period`/`created_at`), cache-wipe durability (SC-004), undo restores 800 + finding reappears +
      `reverted`/`reverted_by`/`reverted_at`, and second-undo `rejected` (FR-008, FR-004).
- [x] T006 [US2] Verify `test_apply_fail_rolls_back_byte_for_byte`, `test_no_op_writes_no_row`, and
      `test_unverifiable_writes_no_row` are left unchanged (FR-005).

## Phase 5: Polish & Cross-Cutting

- [x] T007 Update the module docstring at the top of
      `scripts/integration_tests/test_corrections_d1.py` so its US1/US2/US3 bullet list matches the
      new 4-test layout (FR-007).
- [x] T008 Confirm exactly 4 test methods exist and no unused imports were introduced (FR-001,
      FR-006): `grep -E '    def test_'` returns exactly the four expected names; `import shutil` is
      used.
- [x] T009 Run `pnpm test:py:integration` and confirm `TestCorrectionsD1` reports 4 tests, 0
      failures/errors (SC-001). Also run `pnpm format` so the spec markdown passes the prettier CI
      gate.

## Dependencies

- T001 → T002 → T003 → (T004 → T005) → T006 → T007 → T008 → T009.
- All tasks touch the same file; execute sequentially in the order above. No parallelism.

## Implementation strategy

MVP = the whole feature (it is one small refactor of one file). Apply edits in file order: imports,
`setUp`, delete redundant tests, add lifecycle test, docstring; then verify.
