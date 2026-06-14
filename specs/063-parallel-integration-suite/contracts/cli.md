# Contract: `run_parallel.py` CLI

`scripts/integration_tests/run_parallel.py`, run from `scripts/` via `uv run python -m integration_tests.run_parallel`.

## Parent (default) mode

```
python -m integration_tests.run_parallel [--workers N] [--persist-prefix .wrangler/state-test-w]
```

- Discovers the integration modules (`test_*.py` under `integration_tests/`).
- `--workers N` (optional): cap on worker count; default = `min(module_count, os.cpu_count())`. A value above that cap is clamped down to it.
- `--persist-prefix` (optional): base for per-worker dirs; default `.wrangler/state-test-w` → dirs `…-w0`, `…-w1`, …
- Statically, cost-awarely partitions modules across the workers.
- Spawns each worker as a subprocess in **worker mode** with `SVHC_WRANGLER_PERSIST=<that worker's dir>` in its env.
- Captures each worker's output; on completion prints `RunSummary` (worker count + per-module timing table).
- **Exit code**: `0` iff every module passed and no worker crashed; non-zero otherwise. On failure, replays the failing workers' captured output to stderr/stdout.
- **Cleanup**: removes every per-worker persist dir it created, in a `finally` block, on any exit path.
- **Zero modules**: prints "no integration modules found" and exits `0`.

## Worker mode

```
python -m integration_tests.run_parallel --worker <persist-dir> <module> [<module> ...]
```

- Reads `SVHC_WRANGLER_PERSIST` from its env (set by the parent to `<persist-dir>`).
- Seeds its DB **once** (`_harness.seed_once()` → migrate + synthetic + R2).
- Runs each `<module>` in-process via `unittest` (TextTestRunner), in sequence, reusing the seeded DB.
- Emits one parseable `ModuleResult` line per module (e.g. `##RESULT## {json}`) to stdout.
- **Exit code**: `0` iff all assigned modules passed; `1` otherwise.

## Invariants

- The parent never writes to `.wrangler/state-test` (the shared serial DB) — only to its `…-w<i>` dirs.
- No `--remote` path exists; the runner is local-only.
- The serial fallback (`unittest discover` against `.wrangler/state-test`) remains available unchanged via `pnpm test:py:integration:serial`.
