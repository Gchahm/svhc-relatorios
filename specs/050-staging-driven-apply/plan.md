# Implementation Plan: Staging-driven apply-extractions (safety + per-attachment scoping)

**Branch**: `050-staging-driven-apply` | **Date**: 2026-06-13 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/050-staging-driven-apply/spec.md`

## Summary

`apply_extractions` (in `scripts/analysis/extractions.py`) iterates the pending plan envelopes
from `build_plan` and, for every group, builds + writes the roll-up — including groups whose
representative has **no** recorded `page_classifications` staging rows, which produces an all-empty
analysis that overwrites a prior good one. The fix is a single localized change: in
`apply_extractions`'s group loop, **skip any group whose representative attachment id has no row in
the period's loaded `page_classifications` list**. This is both the safety guard (a pruned/uncrashed
bystander is never visited) and the scoping mechanism (recording staging selects a group for apply).
No schema change, no migration, no change to `build_plan` / `docs-plan` / `mark-pending` / the loader.

## Technical Context

**Language/Version**: Python 3.12 (analysis CLI under `scripts/analysis/`, run via `uv`); test runner is Python stdlib `unittest`.
**Primary Dependencies**: Existing only — `scripts/common/d1.py` (wrangler-CLI wrapper) is touched only indirectly via the unchanged `_merge_and_write`; the selection check reads an in-memory list already loaded by `load_all_periods`. No new pip/npm dependency.
**Storage**: Cloudflare D1 (`DATABASE` → `fiscal-db`). The `page_classifications` staging table is read-only here (presence check); `attachment_analyses` / `attachment_analysis_records` / `attachment_state` are written only for processed groups by the unchanged `_merge_and_write`. **No schema change, no migration.**
**Testing**: stdlib `unittest`. New pure unit test for the selection helper under `scripts/tests/`; new real-D1 integration test under `scripts/integration_tests/` (the destructive-bystander + targeted-reclassify cases) using the feature-046 synthetic seed harness.
**Target Platform**: Linux (the analysis pipeline runs under `uv`); local Miniflare D1/R2 for integration tests.
**Project Type**: single (Python analysis pipeline within the Next.js repo).
**Performance Goals**: No new D1 reads — the staging-presence signal reuses the per-period `page_classifications` list the loader already provides. Skipping groups strictly reduces work.
**Constraints**: Must not change `docs-plan` output, the loader pending query, `mark-pending`, or any processed group's output (byte-identical roll-up). Selection localized to `apply_extractions`.
**Scale/Scope**: One function changed (`apply_extractions`) plus one tiny pure helper for the staging-presence set; two test files added.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- **I. Type Safety & Schema Discipline**: PASS — no schema change, no migration, no auth change. Python-side change; no Drizzle/TS contract touched.
- **II. Cloudflare-Native Architecture**: PASS — all D1 access stays in the existing `scripts/common/d1.py` wrapper via the unchanged `_merge_and_write`; no direct connection, no new binding.
- **III. Quality Gates Before Commit**: PASS — the spec explicitly requests unit + integration tests; both will pass before merge. `pnpm lint`/`pnpm format` apply only to TS (none touched); Python is checked by `pnpm test:py` + `pnpm test:py:integration`. Prettier covers no Python.
- **IV. Security & Auth by Default**: PASS — no route, no auth surface, no data exposure change.
- **V. Simplicity & Incremental Delivery**: PASS — the simplest possible fix (a guard inside the existing loop), explicitly chosen over the rejected `run_selected` column (design doc §4.1+4.2). No new abstraction.

No violations — Complexity Tracking left empty.

## Project Structure

### Documentation (this feature)

```text
specs/050-staging-driven-apply/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/           # Phase 1 output (CLI behaviour contract)
└── tasks.md             # Phase 2 output (speckit tasks)
```

### Source Code (repository root)

```text
scripts/
├── analysis/
│   ├── extractions.py            # CHANGED: apply_extractions skips groups whose
│   │                             #          representative lacks staging rows
│   └── page_classifications.py   # unchanged (read its rows; presence helper may live here)
└── tests/
    └── test_extractions_apply_selection.py   # NEW: pure unit test for the staging-presence filter
scripts/integration_tests/
└── test_apply_staging_driven_d1.py           # NEW: real-D1 bystander + targeted reclassify cases
```

**Structure Decision**: Single-project Python analysis pipeline. The change is confined to
`apply_extractions` in `scripts/analysis/extractions.py`. The staging-presence set is computed from
the already-loaded `periods[period].raw["page_classifications"]` (the same source `build_plan`'s
`recorded` flag and `D1ExtractionProvider` use), so no loader or D1 wrapper change is needed.

## Complexity Tracking

> No constitution violations — section intentionally empty.
