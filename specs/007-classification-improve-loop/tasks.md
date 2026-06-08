---
description: "Task list for 007 — self-improving document-classification loop"
---

# Tasks: Self-Improving Document-Classification Loop

**Input**: Design documents from `/specs/007-classification-improve-loop/`
**Prerequisites**: plan.md ✅, spec.md ✅, research.md ✅, data-model.md ✅, contracts/ ✅

**Tests**: None. The repo has no test framework (Constitution III) and the spec did not request
tests. The deterministic `verdicts.py` helpers are written to be hand-verifiable and are exercised
via `quickstart.md`.

**US1 is already implemented** (the `analyze-docs` agent + `classify-*` skills + the
`python -m analysis` chain satisfy FR-001–FR-003 and FR-005 — confirmed in the Clarifications
session). This branch delivers **US2 + US3** on top of it, plus one small **FR-004 closeout**
(`page_refs` in the mismatch summary — analyze finding C1). There are no other US1 tasks; US1 is
otherwise consumed as-is.

**Organization**: by user story. US2 (P2) is the MVP of this branch; US3 (P3) builds on it.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependency on an incomplete task)
- **[Story]**: US2 / US3 (Setup & Foundational & Polish carry no story label)
- All paths are repo-relative.

## Path Conventions

This feature lives in `scripts/analysis/` (Python, stdlib) and `.claude/agents/` +
`.claude/skills/` (Markdown workers). No `src/` (TypeScript) or D1 changes.

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Create the new analysis module the loop's bookkeeping lives in.

- [X] T001 Create `scripts/analysis/verdicts.py` skeleton: module docstring (cite
  `specs/007-classification-improve-loop/contracts/verdict-cli.md` + `verdicts-file.schema.md`),
  stdlib imports, `VERDICTS_SUFFIX = ".verdicts.json"`, and `verdicts_path(data_dir, period) -> Path`
  plus `_read_json`/`_write_json` helpers (mirror the patterns in `scripts/analysis/extractions.py`).

**Checkpoint**: `python -c "import analysis.verdicts"` imports cleanly from `scripts/`.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: The shared, deterministic primitives BOTH stories need: stable mismatch identity, the
verdict record schema, and load/upsert of the per-period verdicts file.

**⚠️ CRITICAL**: US2 and US3 both depend on these; complete Phase 2 before either story.

- [X] T002 In `scripts/analysis/verdicts.py`, implement `mismatch_key(mismatch: dict) -> str`
  (data-model Decision 4): `period|kind|document_id|entry_id` for per-document kinds and
  `period|kind|sorted(document_ids)` for `duplicate_billing`. Excludes volatile extracted values so a
  re-read does not look like a new mismatch.
- [X] T003 In `scripts/analysis/verdicts.py`, implement the verdicts-file load + upsert + validation
  helpers: `load_verdicts_file(data_dir, period)` (fresh `{period, verdicts: [], loop_state: null}`
  when absent), `validate_verdict(rec)` (verdict ∈ `true|false|transient|page-error`; `root_cause`
  with `area`+non-empty `hypothesis` required iff `verdict=false`; `confidence` ∈ `high|medium|low`),
  and `upsert_verdict(file, rec, iteration)` (latest-wins by `mismatch_key`, idempotent within an
  iteration, history-preserving). Per `contracts/verdicts-file.schema.md`.

**Checkpoint**: identity + validation + file IO available; no CLI yet.

---

## Phase 3: User Story 2 - Review a mismatch as true vs false (Priority: P2) 🎯 MVP (this branch)

**Goal**: An automated, context-isolated Claude-vision worker judges one mismatch (true / false /
transient / page-error, with a root cause for false), and its verdict is persisted deterministically.

**Independent Test** (spec US2): feed the reviewer a known true mismatch and a known false mismatch
(with their images + entries); confirm it labels each correctly and, for the false one, returns a
plausible root-cause hypothesis — then `record-verdict` writes both into `<period>.verdicts.json`.

### Implementation for User Story 2

- [X] T004 [US2] Close FR-004: extend `summarize_mismatches` in `scripts/analysis/extractions.py`
  so every mismatch row includes `page_refs` — `[{document_id, page_label, read_path}]` (absolute
  `read_path`s) for the document(s) behind the mismatch (per-document kinds: the one document;
  `duplicate_billing`: one group per `document_ids[]`). Derive from the document's `file_path` tokens
  (reuse `_page_label_from_path` + `Path(...).resolve()`, as `docs-plan` does). Per `data-model.md`
  (Mismatch) + research Decision 5. Keep the rest of the summary unchanged.
- [X] T005 [US2] In `scripts/analysis/verdicts.py`, implement `record_verdict(...)`: stamp
  `reviewed_at`, run `validate_verdict`, `upsert_verdict`, and support attaching a `FixProposal`
  reference (`fix-branch`/`fix-pr`/`fix-status`/`fix-summary`; reject `fix-status=merged`). Raise on
  schema violation. Per `contracts/verdict-cli.md` (`record-verdict`).
- [X] T006 [US2] Register the `record-verdict` subcommand in `scripts/analysis/__main__.py` (args:
  `--periodo`, `--iteration`, `--json`, `--data-dir`, `--fix-branch/--fix-pr/--fix-status/--fix-summary`;
  wire to `record_verdict`; non-zero exit on validation error) and add it to the module docstring's
  command list.
- [X] T007 [P] [US2] Create the review worker `.claude/agents/review-mismatch.md` per
  `contracts/review-mismatch.agent.md`: frontmatter (`name: review-mismatch`, `tools: Read, Glob,
  Bash`, `model: inherit`, color, description); body that opens the mismatch's `page_refs[].read_path`
  + the ledger entry in `<period>.json`, judges the mismatch, returns ONLY the terse verdict JSON,
  and never writes any file.

**Checkpoint**: invoke `review-mismatch` on one mismatch (whose summary now carries `page_refs`) →
get a verdict; `record-verdict` persists it; `<period>.verdicts.json` shows the record (quickstart
§1). US2 is independently demonstrable.

---

## Phase 4: User Story 3 - The self-improving loop (Priority: P3)

**Goal**: A thin orchestrator runs analyze → review → fix (PR, never merge) → scoped re-run, driven
by deterministic loop state, terminating on convergence / max-iterations / no-progress.

**Depends on**: Phase 2 + US2 (the loop calls `review-mismatch` and `record-verdict`).

**Independent Test** (spec US3): run the orchestrator on a period seeded with one known false
mismatch; confirm it detects → reviews false → delegates a fix PR → re-runs scoped to the affected
document → terminates without auto-merging.

### Implementation for User Story 3

- [X] T008 [US3] In `scripts/analysis/verdicts.py`, implement `loop_state(...)`: join current
  `summarize_mismatches(...)` (imported from `.extractions`) with stored verdicts to compute `open`,
  `findings`, `data_quality`, `affected_document_ids` (docs behind still-open mismatches **only**, so
  converged docs drop out — SC-006; unpack `duplicate_billing.document_ids[]`), append an
  `IterationRecord` to `history`, and set
  `terminate` deterministically — `converged` (no open false/transient-unresolved), `max-iterations`
  (default 3), or `no-progress` (open set didn't shrink, or a key flipped/recurred, across
  `no_progress_window`=2 iterations). Persist the recomputed `loop_state` and return it. Byte-stable
  on unchanged inputs (SC-003). Per `contracts/verdict-cli.md` (`loop-state`) + data-model
  `LoopState`.
- [X] T009 [US3] Register the `loop-state` subcommand in `scripts/analysis/__main__.py` (args:
  `--periodo`, `--iteration`, `--max-iterations`, `--no-progress-window`, `--document-id`,
  `--entry-id`, `--data-dir`; print the `LoopState` JSON to stdout) and add it to the module
  docstring's command list.
- [X] T010 [P] [US3] Create the fix worker `.claude/agents/fix-mismatch.md` per
  `contracts/fix-mismatch.worker.md`: frontmatter (`name: fix-mismatch`, `tools: Bash, Read, Edit,
  Write, Skill, Glob, Grep`, `model: inherit`, color, description); body that branches off `main`,
  runs the `speckit` skill to implement the fix at the hypothesized `area`, verifies via the scoped
  pipeline, opens a PR with `gh` and NEVER merges/pushes to `main`, and returns ONLY the terse result
  JSON (`mismatch_key`, `branch`, `pr_url`, `status` ∈ `pr-open|failed`, `summary`).
- [X] T011 [P] [US3] Create the orchestrator `.claude/skills/improve-classification/SKILL.md` per
  `contracts/orchestrator-loop.md`: a NON-forked skill (runs in the main context so it can spawn
  subagents) implementing the loop — delegate to `analyze-docs`, call `loop-state`, fan out
  `review-mismatch` per open mismatch, `record-verdict` each, delegate `fix-mismatch` for each false,
  rescope to `affected_document_ids`, repeat until `terminate`; argument-hint
  `[period] [--document-id …] [--entry-id …] [--max-iterations N]`; explicit boundaries (delegation
  only, never reads images/diffs, never merges).

**Checkpoint**: `/improve-classification <period>` runs the full loop and halts with a termination
reason; PRs are opened but nothing is merged (quickstart §2). All of US2 + US3 functional.

---

## Phase 5: Polish & Cross-Cutting Concerns

- [X] T012 [P] Update `CLAUDE.md`: add `review-mismatch`, `fix-mismatch`, and the
  `improve-classification` orchestrator skill to the **Agents** section; note that deciding
  true-vs-false and the fix step (previously "separate steps, see 007") now exist; add a short
  **Self-improving classification loop** bullet under *Important Patterns* describing the
  analyze→review→fix→re-run loop, the `page_refs` now in the `mismatches` summary, and the
  `<period>.verdicts.json` working file.
- [X] T013 Run `quickstart.md` end-to-end on one period (e.g. `2025-12`): exercise §1 (manual
  review + `record-verdict` + `loop-state`) and §3 acceptance checks — scoped re-run (SC-001/006),
  deterministic loop-state (SC-003), findings preserved (SC-004), terminates & never merges (SC-005),
  and **verify SC-002**: confirm no page images/diffs appear in the orchestrator's own turns
  (analyze finding C2).

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: no dependencies — start immediately (T001).
- **Foundational (Phase 2)**: depends on T001; **blocks US2 and US3**.
- **US2 (Phase 3)**: depends on Phase 2. Independently testable once complete.
- **US3 (Phase 4)**: depends on Phase 2 **and US2** (it calls `review-mismatch` + `record-verdict`).
- **Polish (Phase 5)**: depends on US2 + US3.

### Within-file ordering (same-file tasks are sequential, NOT parallel)

- `scripts/analysis/verdicts.py`: T001 → T002 → T003 → T005 → T008.
- `scripts/analysis/extractions.py`: T004 (standalone, no other task touches it).
- `scripts/analysis/__main__.py`: T006 → T009.
- New standalone files (parallel-safe): T007, T010, T011, and T012 (CLAUDE.md).

### Parallel Opportunities

- T004 (page_refs, `extractions.py`) is independent of the `verdicts.py` work and can run alongside
  T002/T003/T005, but **must land before** T007 (the review worker consumes `page_refs`).
- T007 [P] (review-mismatch agent) can be written in parallel with T005/T006 (different files).
- T010 [P] (fix-mismatch agent) and T011 [P] (orchestrator skill) can be written in parallel with
  each other and with the T008/T009 Python work — all different files.
- T012 [P] (docs) can proceed once the agents/skills exist.

---

## Parallel Example: User Story 3

```bash
# After T008/T009 (Python loop-state) are underway, author the Markdown workers concurrently:
Task: "Create .claude/agents/fix-mismatch.md per contracts/fix-mismatch.worker.md"          # T010
Task: "Create .claude/skills/improve-classification/SKILL.md per contracts/orchestrator-loop.md"  # T011
```

---

## Implementation Strategy

### MVP for this branch (US2)

1. Phase 1 (T001) → Phase 2 (T002, T003) → Phase 3 (T004–T007).
2. **STOP and VALIDATE**: review a known true and a known false mismatch; confirm labels +
   root-cause; confirm `record-verdict` persists them. This is the spec's US2 Independent Test.

### Incremental Delivery

1. Setup + Foundational → shared primitives ready.
2. US2 (incl. FR-004 `page_refs` closeout) → review + persistence → demo (MVP).
3. US3 → orchestrator loop + fix worker → demo the full self-improving loop (PRs opened, never
   merged, always terminates).

### Notes

- [P] = different files, no incomplete dependency. Same-file tasks (verdicts.py, __main__.py) are
  serialized per the ordering above.
- Keep the deterministic logic in Python (T002, T003, T004, T005, T008) and the
  vision/judgment/codegen in the Markdown workers (T007, T010, T011) — the core architectural seam of
  this feature.
- Commit after each task or logical group; run `pnpm lint`/`pnpm format` only if TS is touched (none
  expected here).
