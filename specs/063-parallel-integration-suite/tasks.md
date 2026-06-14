# Tasks: Parallelize the integration test suite across isolated workers

**Feature**: 063-parallel-integration-suite | **Spec**: [spec.md](./spec.md) | **Plan**: [plan.md](./plan.md)

## Phase 1: Setup

- [x] T001 Confirm dependency #107 is in place: `scripts/common/d1.py:_persist_args` reads `SVHC_WRANGLER_PERSIST` and `scripts/e2e/seed.py:_apply_migrations` honors it; confirm `.wrangler/` is gitignored (so per-worker dirs won't be tracked).

## Phase 2: Foundational

- [x] T002 Add module discovery to `scripts/integration_tests/run_parallel.py`: a `discover_modules()` that returns the sorted distinct dotted module names under `integration_tests/` (`test_*.py`) via `unittest.TestLoader().discover`.

## Phase 3: User Story 1 — Parallel run with per-worker DB isolation (P1)

**Goal**: `pnpm test:py:integration` runs modules in parallel, each worker with its own persist dir; same overall result as serial.
**Independent test**: Run `pnpm test:py:integration`; observe N workers each with a distinct `.wrangler/state-test-w<i>` dir, all tests pass, wall-clock below serial.

- [x] T003 [US1] Implement worker mode in `scripts/integration_tests/run_parallel.py` (`--worker <persist-dir> <module...>`): seed the worker's DB once via `_harness.seed_once()`, then run each module in-process with `unittest.TextTestRunner`, emitting one `##RESULT## {json}` line per module (module, passed, tests_run, duration_s); exit 0 iff all passed.
- [x] T004 [US1] Implement parent mode in `scripts/integration_tests/run_parallel.py`: compute `worker_count = min(len(modules), os.cpu_count())` (clamped by optional `--workers`), cost-awarely partition modules across workers, spawn each as a subprocess with `SVHC_WRANGLER_PERSIST=.wrangler/state-test-w<i>` in its env (via a `ThreadPoolExecutor`), capture stdout/stderr + exit code.
- [x] T005 [US1] Aggregate results in parent: parse `##RESULT##` lines, build the RunSummary, set overall exit non-zero iff any module failed or any worker crashed.
- [x] T006 [US1] Point `pnpm test:py:integration` at the parallel runner in `package.json` (`cd scripts && uv run python -m integration_tests.run_parallel`), keeping the same per-run env hygiene (no fixed `SVHC_WRANGLER_PERSIST` — the runner sets per-worker dirs itself).

## Phase 4: User Story 2 — Serial fallback (P2)

**Goal**: A debugging command runs all modules serially against the single shared test DB (pre-feature behavior).
**Independent test**: `pnpm test:py:integration:serial` runs `unittest discover` against `.wrangler/state-test`.

- [x] T007 [US2] Add `test:py:integration:serial` to `package.json` = the pre-feature command (`cd scripts && SVHC_WRANGLER_PERSIST=.wrangler/state-test uv run python -m unittest discover -s integration_tests -t .`).

## Phase 5: User Story 3 — Clean, observable runs (P3)

**Goal**: Worker count + per-module timings printed; no leftover persist dirs.
**Independent test**: Parallel run logs worker count + a timing table; `.wrangler/` has no `state-test-w*` afterward.

- [x] T008 [US3] In the parent, print the worker count + a per-module timing table (sorted by duration) on completion; on failure, replay the failing workers' captured output.
- [x] T009 [US3] In the parent, remove every per-worker `.wrangler/state-test-w<i>` dir in a `finally` block (regardless of pass/fail), and handle the zero-modules case (print + exit 0).

## Phase 6: Polish & Verification

- [x] T010 Update CI: confirm `.github/workflows/ci.yml` `e2e` job's "Python integration tests" step (`pnpm test:py:integration`) now runs the parallel path (no edit needed if the script name is unchanged — verify and note in the PR). The preceding `pnpm e2e:seed` + following `pnpm test:e2e` keep using `.wrangler/state-test`.
- [x] T011 Verify parity (SC-001): run `pnpm test:py:integration:serial` and `pnpm test:py:integration`; confirm identical pass/fail and test counts, and that parallel wall-clock is materially below serial (SC-002). Confirm no `state-test-w*` dirs remain (SC-004).
- [x] T012 Run `pnpm lint`, `pnpm format`, and `prettier --check .` (the spec/docs markdown); commit any formatting. Confirm no `src/`, schema/migration, or `--remote` change (FR-010).

## Dependencies

- T001 → T002 → (T003, T004) → T005 → T006 (US1 chain; T003/T004 both feed T005).
- US2 (T007) and US3 (T008, T009) depend on the parent existing (T004) but are otherwise independent of each other.
- Polish (T010–T012) after all stories.

## Implementation strategy

MVP = US1 (T001–T006): parallel isolated run replacing the default command. US2 + US3 are small additive scripts/hygiene. All in one PR (the feature is one cohesive runner).
