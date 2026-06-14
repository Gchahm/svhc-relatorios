# Implementation Plan: Trim the 3 heavy integration modules + drop npx wrangler overhead

**Branch**: `062-trim-heavy-integration-tests` | **Date**: 2026-06-14 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/062-trim-heavy-integration-tests/spec.md`

## Summary

Cut the CI `e2e` job's ~32-minute "Python integration tests (real D1 writebacks)" step by applying the proven TEST-005 / PR #106 trim to the three remaining heavy real-D1 modules and resolving the local `wrangler` binary once at import in `scripts/common/d1.py`. The trim removes per-test `h.restore()` (kept in `tearDownClass`) and collapses redundant full-pipeline arranges where the subject is a singleton and assertions are subject-scoped — preserving every assertion and each module's distinct paths. The wrangler change is a flag-preserving executable-location change with an `npx wrangler` fallback.

## Technical Context

**Language/Version**: Python 3 (stdlib `unittest`, no pytest/mock framework beyond `unittest.mock`)
**Primary Dependencies**: `scripts/common/d1.py` (`wrangler`-CLI wrapper), `scripts/e2e` seed/synthetic, local Miniflare D1/R2
**Storage**: Cloudflare D1 (SQLite) via Miniflare locally; `.wrangler/state-test` isolated test DB (`SVHC_WRANGLER_PERSIST`)
**Testing**: `pnpm test:py:integration` (real-D1 integration suite, one process, serial)
**Target Platform**: Local dev container + GitHub Actions `e2e` job
**Project Type**: Single (Python scripts under `scripts/`); no `src/` change
**Performance Goals**: Materially lower step-9 wall-clock (target ≥30–40% of the #106-style trim on these three modules + the npx saving); baseline 1907 s
**Constraints**: No coverage loss; no flag/behavior change on `--remote`; only non-test file touched is `scripts/common/d1.py`; no D1 schema/migration; no `src/` change
**Scale/Scope**: 3 integration modules (re_derive 5 tests, reclassify 3, typed_record 3) + 1 wrapper module

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- **I. Type Safety & Schema Discipline**: No schema change, no migration, no auth schema. PASS.
- **II. Cloudflare-Native Architecture**: D1/R2 access stays through `scripts/common/d1.py`; the wrangler change only changes how the executable is located, not the binding/flag usage. PASS.
- **III. Quality Gates Before Commit**: `prettier --check .` must stay clean (it covers `scripts/`/markdown). The feature explicitly preserves test coverage and the integration suite must pass. PASS.
- **IV. Security & Auth by Default**: No route/auth change; `--remote` (production) behavior unchanged. PASS.
- **V. Simplicity & Incremental Delivery**: Pure reduction — fewer subprocess fan-outs, one resolver, no new abstraction or dependency. PASS.

No violations; Complexity Tracking not required.

## Project Structure

### Documentation (this feature)

```text
specs/062-trim-heavy-integration-tests/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── checklists/
│   └── requirements.md  # spec quality checklist
└── tasks.md             # Phase 2 output (speckit tasks)
```

### Source Code (repository root)

```text
scripts/
├── common/
│   └── d1.py                          # wrangler-CLI wrapper — resolve binary once at import (FR-006/007)
└── integration_tests/
    ├── _harness.py                    # unchanged (seed_once / restore)
    ├── test_re_derive_d1.py           # trim arranges; RETAIN setUp restore() (sibling/group asserts, A2)
    ├── test_reclassify_d1.py          # drop setUp restore() -> tearDownClass; singleton E3, bystander E1
    └── test_typed_record_d1.py        # drop setUp restore() -> tearDownClass; own-rep E4
```

**Structure Decision**: Single-project Python scripts. No `src/` involvement. The only non-test file is `scripts/common/d1.py`.

## Complexity Tracking

No constitution violations; table intentionally empty.
