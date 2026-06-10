---

description: "Task list for 019-skip-apply-materialize"
---

# Tasks: Skip R2 image materialization in apply-extractions when no content_hash backfill is needed

**Input**: Design documents from `/specs/019-skip-apply-materialize/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/apply-materialize-guard.md

**Tests**: No test framework is configured (constitution III — tests OPTIONAL). No automated test
tasks; verification is a manual parity run per quickstart.md.

**Organization**: Tasks grouped by user story. Note: the single foundational predicate
(`attachments_needing_hash_backfill`) plus the guard in `apply_extractions` simultaneously
satisfies all three user stories — its definition ("page-bearing AND missing hash") is exactly what
makes US1 (skip when none), US2 (backfill when missing), and US3 (page-less excluded) hold. The
per-story phases below are therefore validation slices over the same code, not separate code paths.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- File paths are repo-relative.

## Path Conventions

Single Python package: `scripts/analysis/`. Docs at `scripts/README.md`, `scripts/pipeline-flow.md`,
`CLAUDE.md`.

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Confirm the working environment.

- [X] T001 Confirm the analysis CLI runs locally: from `scripts/`, `uv run python -m analysis --help` succeeds (Python 3.12, stdlib-only, no new deps per plan.md).

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: The predicate that every user story relies on.

**⚠️ CRITICAL**: The guard in Phase 3 cannot be written until this exists.

- [X] T002 Add `attachments_needing_hash_backfill(periods, attachment_ids=None) -> list[str]` to `scripts/analysis/images.py` per `contracts/apply-materialize-guard.md`: return in-scope attachment ids that are page-bearing (`_split_tokens(doc.get("file_path"))` non-empty) **and** have a falsy `content_hash`; exclude page-less rows; honor the optional `attachment_ids` scope; pure read (no D1/R2, no mutation). Reuse the existing `_split_tokens` helper.
- [X] T003 Confirm `materialize_period_images` in `scripts/analysis/images.py` is **unchanged** (its signature/behavior must stay identical so the classify/review callers are unaffected — FR-006).

**Checkpoint**: Predicate available and importable; shared materializer untouched.

---

## Phase 3: User Story 1 - Steady-state apply makes no wasted R2 round-trip (Priority: P1) 🎯 MVP

**Goal**: When every page-bearing attachment is already keyed, `apply-extractions` performs zero R2
image downloads while producing identical output.

**Independent Test**: On a fully-keyed DB, run `apply-extractions` and confirm a "skipping R2 image
materialization" log line, no "Materialized N page image(s)" line, and output parity (quickstart
SC-001/SC-002).

### Implementation for User Story 1

- [X] T004 [US1] In `scripts/analysis/extractions.py:apply_extractions`, replace the unconditional `materialize_period_images(periods, cache_dir, target)` call (after `load_all_periods`, before `build_plan`) with the guarded form: compute `needing = attachments_needing_hash_backfill(periods)`; if `needing`, call `materialize_period_images(periods, cache_dir, target, attachment_ids=needing)`; else `logger.info("All page-bearing attachments already have content_hash; skipping R2 image materialization")`. Import the new helper from `.images`.
- [X] T005 [US1] Update the docstring/comment in `apply_extractions` that currently says it materializes images so it states materialization is now conditional on a needed `content_hash` backfill (the apply path reads no image bytes otherwise).

**Checkpoint**: Steady-state apply does no R2 reads; output identical (verify per quickstart).

---

## Phase 4: User Story 2 - Legacy attachments without a grouping key still get backfilled (Priority: P2)

**Goal**: A page-bearing attachment with NULL `content_hash` is still materialized, hashed, grouped
correctly, and backfilled.

**Independent Test**: Clear `content_hash` on one page-bearing attachment, run `apply-extractions`,
confirm its images are fetched (scoped), its key is repopulated, and grouping is correct (quickstart
SC-003).

### Implementation for User Story 2

- [X] T006 [US2] Verify (no code change beyond Phase 3) that the guard passes the needing ids to `materialize_period_images` with the default `backfill_hash=True`, so the scoped fetch + in-memory hash + best-effort D1 backfill all run for the legacy row, and grouping (`nf_groups._group_key`) reads the now-populated hash. Confirm via the quickstart SC-003 procedure.

**Checkpoint**: Legacy/edge rows converge in one run; mixed DBs fetch only the unkeyed rows.

---

## Phase 5: User Story 3 - Page-less attachments are never treated as work (Priority: P3)

**Goal**: An attachment with empty `file_path` (and thus NULL `content_hash`) is never in the
needing set and never triggers a fetch.

**Independent Test**: With all page-bearing rows keyed but a page-less row having NULL `content_hash`,
run `apply-extractions` and confirm the skip path (no downloads) — quickstart FR-004.

### Implementation for User Story 3

- [X] T007 [US3] Verify the `attachments_needing_hash_backfill` predicate (T002) excludes page-less rows: a row with empty/NULL `file_path` is not returned even when `content_hash` is NULL. Confirm via the quickstart FR-004 procedure (no behavioral code change beyond the predicate's definition).

**Checkpoint**: Page-less rows are inert to the guard.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Docs and gates (FR-008).

- [X] T008 [P] Update `scripts/README.md` (the `apply-extractions` section, ~lines 99–113) to state that apply now materializes/backfills **only** attachments whose `content_hash` is NULL (page-bearing); when all are keyed it makes no R2 image reads.
- [X] T009 [P] Update `scripts/pipeline-flow.md` (the apply row/sequence, ~lines 135–138, and the cache/grouping bullets) to reflect the conditional materialization in the apply step.
- [X] T010 [P] Update `CLAUDE.md`'s description of the apply step (the "Attachment analysis" / step-(3) bullet) to note apply only reaches R2 when a `content_hash` backfill is actually needed.
- [X] T011 Run `pnpm lint` and `pnpm format` (constitution III gate). Python files are excluded from Prettier per repo config; confirm no formatting/lint regressions in touched files.
- [X] T012 Run quickstart.md verification (SC-001, SC-002, SC-003, FR-004, FR-006) against local period `2025-12` and record results.

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: none.
- **Foundational (Phase 2)**: after Setup. BLOCKS Phase 3 (the guard imports the predicate).
- **US1 (Phase 3)**: after Foundational. This is the MVP and the only phase with new control flow.
- **US2 (Phase 4) / US3 (Phase 5)**: after Phase 3 — they are validation slices over the same guard
  + predicate; no additional production code.
- **Polish (Phase 6)**: after the code phases; T008–T010 are parallelizable (different files).

### Within Each Story

- T002 (predicate) before T004 (guard uses it).
- T004 before T005 (same file; sequential).
- Verification tasks (T006, T007, T012) after the code they exercise.

### Parallel Opportunities

- T008, T009, T010 (three separate doc files) can run in parallel.

---

## Implementation Strategy

### MVP First (User Story 1)

1. T001 (Setup) → T002–T003 (Foundational predicate) → T004–T005 (guard).
2. **STOP and VALIDATE**: quickstart SC-001/SC-002 (skip + parity). This is shippable on its own.

### Incremental

3. Validate US2 (T006) and US3 (T007) — both already covered by the predicate's definition.
4. Docs + gates (T008–T012).

---

## Notes

- [P] = different files, no dependency. The only production-code edits are T002 (`images.py`) and
  T004–T005 (`extractions.py`).
- No schema change, no migration, no new dependency, no CLI flag change (the
  `backfill-content-hash` maintenance command is out of scope per research Decision 4).
- Commit after the code change (T002–T005) and again after docs (T008–T010).
