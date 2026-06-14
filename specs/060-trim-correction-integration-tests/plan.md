# Implementation Plan: Trim feature-054 correction integration tests

**Branch**: `060-trim-correction-integration-tests` | **Date**: 2026-06-14 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/060-trim-correction-integration-tests/spec.md`

## Summary

Trim the feature-054 data-correction integration suite
(`scripts/integration_tests/test_corrections_d1.py`) so the CI `e2e` job's "Python integration
tests (real D1 writebacks)" step returns to roughly its pre-#99 duration, with **no loss of
real-pipeline coverage**. Two edits, both confined to that one test file: (1) remove the per-test
`h.restore()` from `setUp` (keep it in `tearDownClass`); (2) collapse the four `applied`-path tests
that share the same arrange (stage 800 → correct to 250 → applied) into one end-to-end lifecycle
test (one stage + one apply + one undo) that preserves every assertion. The three distinct-path
tests (rollback, no-op, unverifiable) stay unchanged. `import shutil` moves to module top level.

## Technical Context

**Language/Version**: Python 3 (stdlib `unittest`, no pytest, no mocking framework in this file —
it drives the real pipeline)
**Primary Dependencies**: the project's own `scripts/analysis` package + `scripts/common/d1.py`
(`wrangler`-CLI wrapper) and `scripts/integration_tests/_harness.py`; the real local Miniflare
D1/R2.
**Storage**: local Miniflare D1 (synthetic `2099-01` period; `data_corrections`,
`attachment_analyses`, etc.)
**Testing**: `unittest`, run via `pnpm test:py:integration` (separate discovery path from the fast
`pnpm test:py`).
**Target Platform**: developer/CI Linux container with `wrangler` + applied local migrations.
**Project Type**: single (Python analysis/test tooling under `scripts/`).
**Performance Goals**: halve the integration-test-body subprocess fan-out — 8 `apply_extractions` +
4 `run_analysis` + 0 per-test `restore()` (down from 16 + 9 + 7).
**Constraints**: no change to any non-test file; no D1 schema/migration; no new dependency; no
coverage loss on the rollback/no-op/unverifiable paths; do not stub the real pipeline.
**Scale/Scope**: one test file, ~217 lines → ~4 test methods.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- **I. Type Safety & Schema Discipline** — N/A: no TypeScript, no Drizzle schema, no migration
  touched. PASS.
- **II. Cloudflare-Native Architecture** — N/A: no app DB access path changed; the test continues
  to reach D1 through the existing `scripts/common/d1.py` wrapper via the unchanged harness. PASS.
- **III. Quality Gates Before Commit** — The change is test-only and the project's Python tests run
  via `pnpm test:py:integration`; this feature's verification IS running that suite green. `prettier
  --check .` does not cover `.py`, but `pnpm format`/lint run clean (no JS/TS/MD touched beyond
  specs, which prettier does cover — run `pnpm format` before pushing). PASS.
- **IV. Security & Auth by Default** — N/A: no routes, no auth, no secrets. PASS.
- **V. Simplicity & Incremental Delivery** — This feature IS a simplification (fewer redundant
  tests, less subprocess churn) with no new abstraction or dependency. PASS.

No violations; Complexity Tracking is empty.

## Project Structure

### Documentation (this feature)

```text
specs/060-trim-correction-integration-tests/
├── plan.md              # This file
├── spec.md              # Feature spec
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/           # Phase 1 output (none — no API surface)
└── tasks.md             # Phase 2 output (speckit tasks)
```

### Source Code (repository root)

```text
scripts/
└── integration_tests/
    └── test_corrections_d1.py    # the ONLY file edited by this feature
```

**Structure Decision**: Single-project Python test tooling. The entire change lives in one existing
test module; no new files, directories, or contracts are created (this feature has no API surface).

## Complexity Tracking

> No Constitution Check violations — section intentionally empty.
