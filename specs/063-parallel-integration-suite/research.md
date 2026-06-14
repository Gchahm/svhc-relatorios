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

## Decision 2 — Seed once per worker, reuse across its modules

**Decision**: A worker seeds (migrate + synthetic + R2) its private DB **once** at startup via the existing `_harness.seed_once()` / `e2e.seed.seed(apply_migrations=True)`, then runs each assigned module in-process (`unittest` TestLoader on the module). The `_harness._migrated` flag ensures a second module the same worker runs does not re-migrate.

**Rationale**: The one-time seed (~25 s) is the per-worker fixed cost the issue calls out. Reusing the seeded DB across a worker's modules (when there are more modules than workers) keeps total seed cost = `worker_count × seed`, not `module_count × seed`. Each module's own `setUpClass`→`seed_once()` is idempotent (`INSERT OR REPLACE` on det ids), so running several modules sequentially in one worker is exactly what the serial path already does — just scoped to that worker's DB.

**Alternatives considered**:
- *Seed per module*: simpler but pays the seed cost N times; rejected for cost.
- *One shared pre-seeded DB copied per worker*: file-copy of the Miniflare state dir would skip re-migration, but Miniflare's sqlite file layout/locking makes a cold copy fragile; re-running the deterministic seed is robust and already battle-tested.

## Decision 3 — One module per task, shared queue (dynamic assignment)

**Decision**: Shard at one-module-per-task granularity; submit all modules to the pool and let `min(module_count, cpu_count)` workers pull the next module as they free up.

**Rationale**: Module costs are very uneven (memory: `test_corrections_d1` ~7 min vs. a 1-test module ~1 min). Dynamic pull-based assignment load-balances far better than a static round-robin split, pushing wall-clock toward `slowest_module + seed` (SC-002). Module granularity preserves each module's `setUpClass`/`tearDownClass` semantics (A-001 / non-goal: no intra-module split).

Note on seed amortization: with a thread-pool-of-subprocesses where each *task* is one module and each *subprocess* seeds, a naive design would seed per module. To honor Decision 2, the parent assigns a **batch** of modules to a fixed set of long-lived worker dirs: it pre-creates `W = min(module_count, cpu_count)` worker dirs, statically partitions modules across them, and each worker subprocess seeds once then runs its batch. This trades a little load-balance for the seed-once guarantee. Given the dominant cost is the slow modules, the partition places at most one slow module per worker where possible (sort modules by an estimated/observed cost and round-robin assign), and the seed-once saving outweighs residual imbalance. Final approach: **static cost-aware partition into W worker subprocesses, each seeding once.**

**Alternatives considered**:
- *Dynamic per-module subprocess (seed each)*: best load balance but worst seed cost; rejected.
- *Static partition, seed once per worker* (CHOSEN): best total cost; acceptable balance with cost-aware partitioning.

## Decision 4 — Per-worker persist dirs + cleanup

**Decision**: Worker `i` uses `SVHC_WRANGLER_PERSIST=.wrangler/state-test-w<i>` (relative; resolves against repo root per #107). The parent removes every `.wrangler/state-test-w*` dir it created in a `finally` block after the run (pass or fail).

**Rationale**: Distinct dirs = no cross-worker D1/R2 contention (SC-003). Removal prevents accumulation (SC-004). They are under the gitignored `.wrangler/` tree (FR-008).

## Decision 5 — Aggregation, output, exit code

**Decision**: The parent captures each worker subprocess's stdout/stderr and exit code. Overall exit = non-zero iff any worker failed. On success it prints a compact per-module timing table + the worker count. On failure it replays the failing workers' captured output so the failure is diagnosable (the Clarifications decision). Per-module timing is measured by the worker and emitted as a parseable line the parent collects.

**Rationale**: Interleaving live output from concurrent workers is unreadable; capture-and-replay-on-failure keeps logs clean while preserving diagnosability (FR-005, FR-007).

## Decision 6 — Serial fallback

**Decision**: Keep a `pnpm test:py:integration:serial` script = the pre-feature `SVHC_WRANGLER_PERSIST=.wrangler/state-test uv run python -m unittest discover -s integration_tests -t .`. The parallel runner is the new default behind `pnpm test:py:integration`.

**Rationale**: FR-006 / US2 — a known-good single-DB serial path for debugging and as a parity oracle (SC-001).
