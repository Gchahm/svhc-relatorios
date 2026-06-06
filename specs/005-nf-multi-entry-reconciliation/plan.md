# Implementation Plan: Reconcile a single Nota Fiscal shared across multiple entries

**Branch**: `005-nf-multi-entry-reconciliation` | **Date**: 2026-06-06 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/005-nf-multi-entry-reconciliation/spec.md`

## Summary

The scraper attaches one Nota Fiscal to several accountability entries (line-item splits, principal vs. `JUROS/MULTAS`). Today document analysis compares the full NF total against each single fractional entry, raising a false amount-mismatch for every sibling and never detecting the over-claim fraud counterpart. This plan introduces **content-hash grouping of sibling documents**, **group-level amount reconciliation** (`sum(siblings) ≈ NF total`), **dedup of the vision pass** (analyze each unique NF once), and a **`duplicate_billing` alert** when siblings over-claim the NF total. All work lives in the Python analysis pipeline (`scripts/scraper/analise/`); no D1 schema change and no UI change are required — corrected `amount_match` flows through the existing document-analyses view and the new alert renders generically in the existing alerts view.

## Technical Context

**Language/Version**: Python 3.11+ (scraper/analysis pipeline under `scripts/scraper/`)
**Primary Dependencies**: `mlx_vlm` (VLM, already used by `documentos.py`); stdlib `hashlib` for content hashing; no new third-party deps
**Storage**: Period JSON files under `data/scrape/<YYYY-MM>.json` (source of truth for the pipeline); Cloudflare D1 downstream via `scripts/import-to-d1.mjs` (read/import only, schema unchanged)
**Testing**: None configured (constitution Principle III — tests OPTIONAL). Verification is by re-running analysis over the fixtures in `data/scrape/` and asserting outcomes against the issue's confirmed examples.
**Target Platform**: Local CLI pipeline (`python -m scraper ...`) producing JSON; downstream Next.js 15 / Cloudflare app reads imported data
**Project Type**: Web app with a side-car Python data pipeline; this feature touches only the pipeline
**Performance Goals**: Reduce redundant VLM passes — each unique shared NF analyzed once (e.g. 1 pass instead of 4 for the `1057` quad)
**Constraints**: Must not regress the single-entry common case; reuse the existing 5% / R$ 0.05 tolerance; degrade gracefully when the NF total is unextractable
**Scale/Scope**: ~130 documents / ~2800 entries per period; a handful of multi-entry NF groups per period (2 groups in `2025-12`, 2 in `2026-01`)

## Constitution Check

_GATE: Must pass before Phase 0 research. Re-check after Phase 1 design._

- **I. Type Safety & Schema Discipline**: PASS — no D1 schema change; the `document_analyses.amount_match` boolean and `alerts` table already exist and absorb the corrected values / new alert type. No Drizzle/migration changes. (Python pipeline is outside the TS schema, but we keep the JSON shape compatible with the existing importer.)
- **II. Cloudflare-Native Architecture**: PASS — no runtime/binding changes; the app continues to read D1 via `getDb()`. Pipeline writes JSON only.
- **III. Quality Gates Before Commit**: PASS — `pnpm lint`/`pnpm format` run before commit; no TS changes expected, but format is run regardless. No test framework is mandated; verification is fixture-based.
- **IV. Security & Auth by Default**: PASS — no new routes or data exposure; the new alert reuses the protected alerts pipeline.
- **V. Simplicity & Incremental Delivery**: PASS — one small shared grouping helper, reused by the analysis stage and the new check; no new dependency or abstraction beyond what the feature needs. Delivered as P1 (reconciliation) → P2 (over-claim alert) → P3 (dedup) increments.

**Result**: PASS — no violations; Complexity Tracking not required.

## Project Structure

### Documentation (this feature)

```text
specs/005-nf-multi-entry-reconciliation/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/           # Phase 1 output (function/data contracts — no HTTP API)
│   └── nf-grouping.md
└── tasks.md             # Phase 2 output (speckit tasks)
```

### Source Code (repository root)

```text
scripts/scraper/analise/
├── nf_groups.py         # NEW: shared content-hash grouping of sibling documents
├── documentos.py        # CHANGED: dedup VLM per group + group-level amount reconciliation
├── checks/
│   ├── consistency.py   # (reference for Alert/_alert pattern)
│   ├── advanced.py      # CHANGED: add check_duplicate_billing (or new module imported here)
│   └── __init__.py      # CHANGED: register the new check in run_all_checks
├── models.py            # (Alert, PeriodData — possibly expose document_analyses helper)
└── __init__.py          # run_analysis writes alerts (unchanged)

scripts/import-to-d1.mjs # UNCHANGED — already imports alerts + document_analyses
src/                     # UNCHANGED — alerts + document-analyses views render generically
CLAUDE.md                # CHANGED: document grouping/reconciliation + duplicate_billing alert
```

**Structure Decision**: Single side-car Python pipeline. A new `nf_groups.py` holds the grouping logic so both the analysis stage (`documentos.py`, Stories 1 & 3) and the alert check (Story 2) share one definition of "same NF". The alert is emitted by the checks pipeline because that pipeline owns the `alerts` array in the period JSON (`analise/__init__.py` overwrites `raw["alerts"]`); emitting from `documentos.py` would be clobbered by a later checks run.

## Complexity Tracking

> No constitution violations — section intentionally empty.
