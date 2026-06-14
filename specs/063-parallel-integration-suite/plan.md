# Implementation Plan: Parallelize the integration test suite across isolated workers

**Branch**: `063-parallel-integration-suite` | **Date**: 2026-06-14 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/063-parallel-integration-suite/spec.md`

## Summary

Replace the serial `unittest discover` invocation behind `pnpm test:py:integration` with a small stdlib parallel runner (`scripts/integration_tests/run_parallel.py`) that discovers the integration modules, shards them one-per-task across a bounded pool of worker subprocesses — each worker pinned to its **own** `SVHC_WRANGLER_PERSIST=.wrangler/state-test-w<i>` dir (the #107 mechanism) — has each worker migrate+seed its DB once then run its assigned module(s), aggregates per-module pass/fail into one exit code, and cleans up the per-worker dirs. The existing serial behavior is preserved as a `pnpm test:py:integration:serial` escape hatch. CI's `e2e` job uses the parallel path; no schema, `src/`, or `--remote` change.

## Technical Context

**Language/Version**: Python 3.12 (the `scripts/` toolchain; run via `uv run`)
**Primary Dependencies**: stdlib only — `subprocess`, `concurrent.futures` (or a worker pool over `multiprocessing`/threads spawning subprocesses), `unittest` (discovery for the module list), `os`, `shutil`, `time`. Reuses `scripts/common/d1.py`'s `SVHC_WRANGLER_PERSIST` selector and `scripts/e2e/seed.py`. No new dependency.
**Storage**: Local Miniflare D1/R2 per worker, under `.wrangler/state-test-w<i>/` (gitignored).
**Testing**: The integration modules themselves (`scripts/integration_tests/test_*_d1.py`) are the workload; this runner is test infrastructure. Its own correctness is validated by running the real suite and comparing to serial (SC-001).
**Target Platform**: Linux (CI `ubuntu-latest`) + local dev container.
**Project Type**: single (Python test-infra utility under `scripts/`).
**Performance Goals**: Wall-clock ≈ slowest module + one seed (SC-002), bounded by `min(module_count, cpu_count)` workers.
**Constraints**: No cross-worker DB interference (SC-003); clean up persist dirs (SC-004); no D1 schema/migration/`src`/`--remote` change (FR-010).
**Scale/Scope**: ~10 integration modules / ~30 tests today; grows by one module per future feature.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- **I. Type Safety & Schema Discipline** — N/A to TS; **no D1 schema change, no migration** (FR-010). PASS.
- **II. Cloudflare-Native Architecture** — all D1/R2 access stays through `scripts/common/d1.py`; isolation is the existing `--persist-to` selector, not a new binding or direct connection. PASS.
- **III. Quality Gates Before Commit** — `pnpm lint` + `pnpm format` (Prettier covers the `scripts/` Python? No — Python is not Prettier-formatted; markdown specs ARE). Run `prettier --check .` before pushing for the docs; the Python follows the existing `scripts/` style. The feature itself is test tooling; its "test" is the comparison run. PASS.
- **IV. Security & Auth by Default** — no routes, no auth surface, local-only, `--remote` explicitly untouched. PASS.
- **V. Simplicity & Incremental Delivery** — stdlib-only, one new file + two package-script edits + one CI line; no new abstraction beyond a thin runner. PASS.

No violations → Complexity Tracking empty.

## Project Structure

### Documentation (this feature)

```text
specs/063-parallel-integration-suite/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/           # Phase 1 output (the runner's CLI contract)
└── tasks.md             # Phase 2 output (speckit tasks)
```

### Source Code (repository root)

```text
scripts/
├── integration_tests/
│   ├── run_parallel.py        # NEW — the parallel runner (module discovery, worker pool, aggregation, cleanup)
│   ├── _harness.py            # unchanged (each worker imports it; the module-level _migrated flag is per-process)
│   └── test_*_d1.py           # unchanged — the workload modules
├── common/d1.py               # unchanged — reuses _persist_args / SVHC_WRANGLER_PERSIST
└── e2e/seed.py                # unchanged — each worker calls seed(apply_migrations=True) once

package.json                   # EDIT — test:py:integration → parallel runner; add test:py:integration:serial
.github/workflows/ci.yml       # EDIT — (no change needed if the npm script name is unchanged; the e2e seed step stays)
```

**Structure Decision**: Single Python utility under `scripts/integration_tests/`, the home of the suite it parallelizes. It reuses the existing seed + persist machinery; no new top-level module or package.

## Phase 0: Research

See [research.md](./research.md). Key decisions:

- **Worker model**: each worker is a **subprocess** running `python -m unittest <module>` with `SVHC_WRANGLER_PERSIST` set in its env to a worker-private dir — not in-process threads. Rationale: the persist-dir selector + the `_migrated` global are read per-process; subprocess isolation is the cleanest way to give each worker its own env and avoid any shared mutable state. A `ThreadPoolExecutor` in the runner orchestrates the subprocesses (the work is I/O-bound on wrangler).
- **Seed-per-worker, not per-module**: a worker seeds its dir once (first module triggers migrate+seed), then reuses it. Achieved by having each worker run a small driver (`python -m integration_tests.run_parallel --worker <dir> <module...>`) that seeds once then runs each assigned module in-process via `unittest`. Reusing the existing `_harness.seed_once()` keeps the migrate-once flag honored.
- **Sharding/assignment**: one module per task, pulled from a shared queue by `min(module_count, cpu_count)` workers — a worker that finishes early picks up the next module (good load balance for uneven module costs).
- **Cleanup**: remove each `.wrangler/state-test-w<i>` dir after the run (try/finally), regardless of pass/fail.

## Phase 1: Design & Contracts

- [data-model.md](./data-model.md) — the (lightweight) entities: Module, Worker, PersistDir, ModuleResult, RunSummary.
- [contracts/cli.md](./contracts/cli.md) — the runner's CLI surface and exit-code contract.
- [quickstart.md](./quickstart.md) — how to run parallel vs. serial, and how to debug a single module.

Post-design Constitution re-check: still PASS (no new surface introduced by the design).

## Complexity Tracking

> No constitution violations — table intentionally empty.
