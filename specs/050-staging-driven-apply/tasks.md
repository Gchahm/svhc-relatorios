# Tasks: Staging-driven apply-extractions (safety + per-attachment scoping)

**Feature**: `050-staging-driven-apply` | **Spec**: [spec.md](./spec.md) | **Plan**: [plan.md](./plan.md)

Tests are explicitly requested by the spec (unit + integration, incl. the destructive-bystander case).

## Phase 1: Setup

- [x] T001 Confirm the working tree is on branch `050-staging-driven-apply` and the analysis test commands run (`pnpm test:py` for unit, `pnpm test:py:integration` for real-D1) so new tests can be exercised locally.

## Phase 2: Foundational

(No blocking prerequisites — the change is one localized edit. No schema/migration.)

## Phase 3: User Story 1 — Re-running apply never destroys a good analysis (P1)

**Goal**: A pending attachment whose group representative has no `page_classifications` staging rows is skipped (left intact), never overwritten with an empty roll-up.

**Independent test**: Seed a period with a pending paged attachment that has an existing analysis but no staging; run `apply-extractions`; assert the analysis + records are unchanged and the attachment is still pending.

- [x] T002 [US1] In `scripts/analysis/extractions.py` `apply_extractions`, build a per-period `staged_ids: set[str]` from `periods[period].raw.get("page_classifications", [])` (the `attachment_id` of each row) and **skip** any group whose `group["representative_attachment_id"]` is not in `staged_ids` — before building/writing its roll-up; the skip touches nothing (no read, no write, no stamp). Add a `logger.debug`/`logger.info` skip note. Keep the existing per-period "Applied N analysis row(s)" log reflecting only processed rows.
- [x] T003 [P] [US1] Add a pure unit test `scripts/tests/test_extractions_apply_selection.py` that exercises the selection predicate over a synthetic plan envelope + `page_classifications` list: a group whose representative id is present is selected; a group whose representative id is absent (incl. when only siblings would have rows) is skipped; an `{"error": ...}` staging row still counts as present. Refactor the predicate into a tiny importable helper if needed so the test does not require D1.
- [x] T004 [US1] Add a real-D1 integration test case in `scripts/integration_tests/test_apply_staging_driven_d1.py` (feature-046 harness): using the synthetic seed, take a **classified** attachment that owns an analysis (E3), mark it pending (clearing its staging — E3 has none) so it is pending-without-staging, run `apply_extractions("local", ["2099-01"])`, and assert its `attachment_analyses` row + `attachment_analysis_records` are unchanged (same row count, same `document_number`) and it remains pending (`classified_at IS NULL`). This is the destructive-bystander guard (SC-001 / INV-1).

## Phase 4: User Story 2 — Targeted single-attachment reclassify (P2)

**Goal**: Recording one attachment's staging then running apply rolls up only that attachment's group; everything else is untouched.

**Independent test**: Two pending paged attachments; record staging for only one; apply; only that one is (re)built + stamped, the other is left pending with no analysis.

- [x] T005 [US2] Extend `scripts/integration_tests/test_apply_staging_driven_d1.py` with a targeted-reclassify case: ensure exactly one attachment (E4, the seeded pending-with-staging attachment) has staging while a second attachment is pending-without-staging; run `apply_extractions("local", ["2099-01"])`; assert E4 gets its analysis built + `classified_at` stamped + its staging pruned, and the second attachment is untouched (still pending, no analysis written by this run). (SC-002 / INV-2.)

## Phase 5: Polish & Cross-Cutting

- [x] T006 Update the module docstring of `apply_extractions` in `scripts/analysis/extractions.py` to state the new selection rule (process only groups whose representative has staging rows; pending-without-staging is skipped, self-heals), replacing the now-stale "the set processed is exactly the pending set" wording.
- [x] T007 Update `CLAUDE.md` — the `Attachment analysis (Claude vision skills)` / feature-035 area — to note that `apply-extractions` is **staging-driven** (feature 050 / issue #84): it rolls up only groups whose representative has `page_classifications` rows, so a pending bystander without staging is never overwritten, and "reclassify exactly attachment X" = record X's staging → apply (the manual pending-set isolation step is retired).
- [x] T008 Update the runbook `docs/features/...`/`docs/runbooks` document referenced by the issue (the `fix-document-vision-mismatch.md` Problem #2 manual isolation step) to reflect that the isolation workaround is no longer needed. If the runbook does not exist under that path, skip and note it in the PR body.
- [x] T009 Run `pnpm test:py` and `pnpm test:py:integration`; ensure all pass (new + existing). Run `pnpm format` (no-op for Python but confirms no TS drift).

## Dependencies & Order

- T001 → T002 → (T003 ∥ T004) → T005 → T006 → T007 → T008 → T009.
- T002 is the single load-bearing code change; both user stories depend on it. T003 is pure and parallelizable with T004.

## Implementation Strategy

MVP = US1 (the safety guard, T002 + T003 + T004). US2 (T005) is a thin additional assertion that the same one change already satisfies (recording staging = selecting for apply). Polish (T006–T009) documents and verifies.
