# Quickstart: Parallel integration suite

## Run the whole suite in parallel (default)

```bash
pnpm test:py:integration
```

Spawns `min(module_count, cpu_count)` worker processes, each with its own isolated Miniflare D1/R2
state (`.wrangler/state-test-w0`, `…-w1`, …). Prints the worker count + per-module timings and exits
non-zero if any module failed. Per-worker dirs are cleaned up afterward.

## Debug a single module (serial fallback)

```bash
pnpm test:py:integration:serial
# or, one module against the shared test DB:
cd scripts && SVHC_WRANGLER_PERSIST=.wrangler/state-test uv run python -m unittest -v integration_tests.test_merge_and_write_d1
```

The serial command runs every module in one process against the single shared `.wrangler/state-test`
DB — the pre-feature behavior — and is the parity oracle for the parallel run.

## Verify parity (SC-001)

Run both and confirm identical pass/fail and test counts:

```bash
pnpm test:py:integration:serial   # baseline
pnpm test:py:integration          # parallel — same result, less wall-clock
```

## CI

The `e2e` job's "Python integration tests" step runs `pnpm test:py:integration` (now the parallel
path). The preceding `pnpm e2e:seed` step and the following `pnpm test:e2e` browser smoke continue to
use the shared `.wrangler/state-test`, untouched by the per-worker dirs.
