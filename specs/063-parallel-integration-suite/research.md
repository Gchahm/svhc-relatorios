# Phase 0 Research: Parallel integration runner

## Decision 1 — Worker model: subprocess per worker, orchestrated by a thread pool

**Decision**: Each worker is a child process invoked as `python -m integration_tests.run_parallel --worker <persist-dir> <module...>` with `SVHC_WRANGLER_PERSIST` set to a worker-private dir in its environment. The parent runner orchestrates them with a `concurrent.futures.ThreadPoolExecutor` (the threads only block on `subprocess.run`, so the GIL is irrelevant) of size `min(module_count, cpu_count)`.

**Rationale**:
- `scripts/common/d1.py:_persist_args` reads `SVHC_WRANGLER_PERSIST` from `os.environ` at call time, and `_harness._migrated` is a process-global flag. Both are naturally per-process when each worker is its own subprocess — no shared mutable state, no race.
- The actual work (wrangler `d1 execute`/`r2`) is itself a fan-out of subprocesses; the integration tests are I/O-bound, so a thread pool around `subprocess.run` gives full concurrency without `multiprocessing` pickling concerns.
- One re-entrant entrypoint (`run_parallel.py` with a `--worker` mode) avoids a second file and keeps the seed-once + module-run logic in the same place the parent already imports for discovery.

**Alternatives considered**:
- *`multiprocessing.Pool` running modules in-process*: would share the parent's already-imported `_harness` and need careful per-process env mutation; subprocess env isolation is simpler and matches how the suite already shells out.
- *Pure `pytest-xdist`*: rejected — the suite deliberately uses stdlib `unittest` (no pytest); adding `pytest-xdist` violates the no-new-dependency constraint (Constitution V) and the documented "no pytest" stance.

## Decision 2 — Migrate once per worker; RESET to baseline before EACH module

**Decision**: A worker applies migrations **once** at startup, then **resets its DB to the clean seed baseline before every module** it runs (not just once). The first module's reset is the full `e2e.seed.seed(apply_migrations=True)`; each subsequent module's reset is `_reset_db` = DELETE-all-rows (every seed table, child→parent, under `PRAGMA defer_foreign_keys = ON`) + `seed(apply_migrations=False)`. Migrations are not reapplied between modules (schema is stable).

**Rationale (corrected during implementation)**: An initial design seeded once per worker and reused the DB across its modules, relying on each module's idempotent `setUpClass`→`seed_once()`. **This is unsafe when modules share a worker DB**: an idempotent `INSERT OR REPLACE` re-seed cannot remove a row a *prior* module **added** (e.g. `test_merge_and_write_d1` stamps the seed-PENDING attachment E4 by inserting an `attachment_state` row; `test_seed_d1` then asserts E4 is pending and fails — observed on CI run 27503447935, 4 workers). A module may also hard-delete mirror rows (reconcile cascade) or prune `documents`. A whole-DB DELETE-then-reseed before each module heals all three classes of contamination, so the parallel result is byte-identical to the isolated serial result. The per-module reset (DELETE + reseed, no re-migrate) is cheap relative to module runtimes (the dominant cost is a few multi-minute modules), so SC-002 still holds (measured: 4 workers, 37 tests, ~570 s wall-clock vs. the serial sum ~60 min).

**Alternatives considered**:
- *Seed once per worker, reuse* (originally chosen, REJECTED): cross-module contamination — see above.
- *Scoped `_harness.restore()` between modules*: only resets the synthetic period's analysis-owned rows and does not rebuild `documents` or undo mirror deletes; insufficient for the general case.
- *Wipe the persist dir + re-migrate per module*: fully correct but pays re-migration each time; the DELETE-all-rows reset is the same correctness without the migration cost.

## Decision 3 — One module per task, shared queue (dynamic assignment)

**Decision**: Shard at one-module-per-task granularity; submit all modules to the pool and let `min(module_count, cpu_count)` workers pull the next module as they free up.

**Rationale**: Module costs are very uneven (memory: `test_corrections_d1` ~7 min vs. a 1-test module ~1 min). Dynamic pull-based assignment load-balances far better than a static round-robin split, pushing wall-clock toward `slowest_module + seed` (SC-002). Module granularity preserves each module's `setUpClass`/`tearDownClass` semantics (A-001 / non-goal: no intra-module split).

Implementation shape: the parent pre-creates `W = min(module_count, cpu_count)` worker dirs and statically round-robins the sorted module list across them (a cost-aware proxy — keeps at most ~one slow module per worker). Each worker subprocess migrates once and **resets to baseline before each module** it runs (Decision 2). Final approach: **static round-robin partition into W worker subprocesses, each migrating once and resetting per module.**

**Alternatives considered**:
- *Dynamic per-module subprocess pool (one fresh dir + full migrate+seed per task)*: best load balance and trivially correct, but pays migration per module; the static-partition + DELETE-reseed reset achieves the same correctness at lower cost.
- *Static partition, seed once per worker (no per-module reset)*: lowest cost but **incorrect** — cross-module contamination (see Decision 2). Rejected.

## Decision 4 — Per-worker persist dirs + cleanup

**Decision**: Worker `i` uses `SVHC_WRANGLER_PERSIST=.wrangler/state-test-w<i>` (relative; resolves against repo root per #107). The parent removes every `.wrangler/state-test-w*` dir it created in a `finally` block after the run (pass or fail).

**Rationale**: Distinct dirs = no cross-worker D1/R2 contention (SC-003). Removal prevents accumulation (SC-004). They are under the gitignored `.wrangler/` tree (FR-008).

## Decision 5 — Aggregation, output, exit code

**Decision**: The parent captures each worker subprocess's stdout/stderr and exit code. Overall exit = non-zero iff any worker failed. On success it prints a compact per-module timing table + the worker count. On failure it replays the failing workers' captured output so the failure is diagnosable (the Clarifications decision). Per-module timing is measured by the worker and emitted as a parseable line the parent collects.

**Rationale**: Interleaving live output from concurrent workers is unreadable; capture-and-replay-on-failure keeps logs clean while preserving diagnosability (FR-005, FR-007).

## Decision 6 — Serial fallback

**Decision**: Keep a `pnpm test:py:integration:serial` script = the pre-feature `SVHC_WRANGLER_PERSIST=.wrangler/state-test uv run python -m unittest discover -s integration_tests -t .`. The parallel runner is the new default behind `pnpm test:py:integration`.

**Rationale**: FR-006 / US2 — a known-good single-DB serial path for debugging and as a parity oracle (SC-001).
