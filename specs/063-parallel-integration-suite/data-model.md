# Phase 1 Data Model: Parallel integration runner

This feature has no persisted data model (no D1 schema). The "entities" are in-process runtime
structures of the runner.

## Module (str)

The dotted import path of one integration test module, e.g. `integration_tests.test_merge_and_write_d1`. Discovered via `unittest.TestLoader().discover('integration_tests', pattern='test_*.py')`, deduped to the set of distinct `__module__` names. The unit of sharding.

## Worker

- **index** `i` (0-based) — identifies the worker.
- **persist_dir** — `.wrangler/state-test-w<i>` (relative to repo root).
- **modules** — the static partition of Modules assigned to this worker.
- **lifecycle** — spawned as a subprocess `python -m integration_tests.run_parallel --worker <persist_dir> <module...>`; seeds its DB once, runs its modules in sequence, exits with 0 (all passed) or 1 (any failed).

## PersistDir

A `.wrangler/state-test-w<i>` directory holding one worker's Miniflare D1 + R2 state. Created on demand by the first wrangler call in that worker; removed by the parent after the run.

## ModuleResult

Per-module outcome the worker emits on a parseable line and the parent aggregates:
- **module** (str)
- **passed** (bool)
- **tests_run** (int)
- **duration_s** (float)

## RunSummary

Parent-side aggregate printed at the end:
- **worker_count** (int) = `min(len(modules), cpu_count)`
- **module_results** (list[ModuleResult])
- **overall_passed** (bool) = all module_results passed AND no worker crashed
- **wall_clock_s** (float)

The process exit code is `0` iff `overall_passed`.
