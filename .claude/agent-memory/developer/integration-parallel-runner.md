---
name: integration-parallel-runner
description: pnpm test:py:integration is a parallel runner (scripts/integration_tests/run_parallel.py); per-worker isolated .wrangler/state-test-w<i> dirs; each worker resets DB to seed baseline BEFORE every module
metadata:
  type: project
---

`pnpm test:py:integration` runs `scripts/integration_tests/run_parallel.py` (feature 063 / DX-002 / #109), NOT `unittest discover`. It shards modules one-per-task across `min(module_count, cpu_count)` worker SUBPROCESSES, each pinned to its own `SVHC_WRANGLER_PERSIST=.wrangler/state-test-w<i>` dir (the #107 selector). Serial fallback for debugging one module: `pnpm test:py:integration:serial` (shared `.wrangler/state-test`).

**Load-bearing correctness rule — reset before EACH module, not once per worker.** When `module_count > cpu_count` (CI: 10 modules / 4 cores) a worker runs several modules against ONE persist dir. Seeding once and reusing is UNSAFE: an idempotent `INSERT OR REPLACE` re-seed cannot remove a row a *prior* module ADDED. Concrete failure (CI run 27503447935): `test_merge_and_write_d1` inserts an `attachment_state` row stamping the seed-PENDING attachment E4 classified; the next module on that worker, `test_seed_d1`, asserts E4 is pending (`classified_at IS NULL`) and fails with `AssertionError: <ts> is not None`. The runner therefore **migrates once, then resets to the clean seed baseline before every module**: `_reset_db` = DELETE all rows from every seed table (child→parent, under `PRAGMA defer_foreign_keys=ON`, incl. `attachment_state` which is not in `d1.TABLE_ORDER`) + `e2e.seed.seed(apply_migrations=False)`. Scoped `_harness.restore()` is insufficient (skips `documents`, doesn't undo mirror hard-deletes). Re-migrating per module would also work but costs more.

**Why:** Adding any new integration module that mutates the synthetic period (stamps state, prunes documents, hard-deletes mirror rows) is safe in parallel ONLY because of the per-module reset. If you change the reset to "seed once per worker", cross-module contamination returns. Relates to [[integration-tests-serial-shared-db]] (the same shared-DB hazard, now solved by reset-per-module rather than forced serial) and [[local-db-persist-selector]] (the #107 mechanism it builds on).

**How to apply:** When a parallel integration run fails but the serial run (or the module alone) passes, suspect cross-module state the reset doesn't cover — check `_reset_db`'s delete list includes the table the failing module reads. Verify locally with `--workers 4` (forces CI-like batching) before pushing, not the local default of one-worker-per-module (which hides contamination because each module gets its own dir).
