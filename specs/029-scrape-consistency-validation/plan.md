# Implementation Plan: Scrape-time consistency validation

**Branch**: `029-scrape-consistency-validation` | **Date**: 2026-06-12 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/029-scrape-consistency-validation/spec.md`

## Summary

After a period's rows are upserted and portal-deletion reconciliation runs (the existing scrape-success path), cross-check the period's three in-memory views of the money — per-`(subcategory, movement_type)` entry sums vs. recorded category subtotals, and subtotal-by-movement-type sums vs. the demonstrativo revenue/expense totals. Any discrepancy beyond the reused reconciliation tolerance produces one idempotent, period-scoped `scrape_inconsistency` `warning` alert (recorded via the existing atomic delete-then-insert convention with resolution-graft), a prominent run-log warning, and a note appended to the scrape run's `errors` field. The detection + alert/SQL construction is a pure, stdlib-only module (`scripts/scraper/consistency.py`) mirroring `reconcile.py`/`preserve.py`; the impure D1 reads/write stay in `runner.py`. No schema migration, no new dependencies, no mirror-table change.

## Technical Context

**Language/Version**: Python 3.12 (scraper under `scripts/scraper/`, run via `uv`); the pure detection module is stdlib-only so it imports without `playwright`.
**Primary Dependencies**: Existing only — `scripts/common/d1.py` (wrangler-CLI wrapper: `query` / `execute_sql`), `scripts/common` (`det_id`, `now_ms`). No new pip/npm deps.
**Storage**: Cloudflare D1 (`DATABASE` → `fiscal-db`). Writes the analysis-owned `alerts` table (existing) and the `scrape_runs.errors` field (existing). Reads nothing new — the entries/subtotals/demonstrativo are already in the in-memory period payload; the only D1 read is the existing per-period prior-alert resolution read (mirrors `reconcile.py`).
**Testing**: Python stdlib `unittest` in `scripts/tests/` (run `python -m unittest discover -s scripts/tests -t scripts`), mirroring `test_reconcile.py` / `test_attachment_preserve.py`. The pure module is directly unit-testable.
**Target Platform**: Cloudflare Workers (frontend, unchanged); the scraper is a local/CI Python CLI writing D1 via `wrangler`.
**Project Type**: Web app + Python pipeline (this feature touches only the Python scraper + the existing alerts surface — no frontend code change).
**Performance Goals**: Negligible — one extra in-memory pass over a period's entries/subtotals (hundreds of rows) plus one tiny D1 read + one batched write per period. No extra portal round-trip.
**Constraints**: Must not write to mirror tables (`entries`/`attachments`/`category_subtotals`/`approvers`/`accountability_reports`); must run only on the scrape-success path; the writeback must be one atomic D1 batch; must not import the analysis package from the scraper (subsystem decoupling).
**Scale/Scope**: ~50 periods, a few hundred entries each. One new pure module + a small hook in `_scrape_periodo`/`run_scrape`, plus a unit-test file. No migration.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- **I. Type Safety & Schema Discipline** — PASS. No schema change (reuses the existing `alerts` table and `scrape_runs.errors`), so no Drizzle migration is needed and the generated schema stays the source of truth. No TypeScript touched.
- **II. Cloudflare-Native Architecture** — PASS. All D1 access goes through the existing `scripts/common/d1.py` wrangler wrapper (`query`/`execute_sql`); no new bindings, no direct connections.
- **III. Quality Gates Before Commit** — PASS. `pnpm lint` + `pnpm format` run before commit (no TS changed, but run regardless). The spec requests tests, so stdlib `unittest` coverage for the pure module is added and must pass.
- **IV. Security & Auth by Default** — PASS. No new route, no new data exposure; the alert flows through the already-auth-gated `/api/alerts` + dashboard.
- **V. Simplicity & Incremental Delivery** — PASS. A pure-function module + a thin runner hook, reusing the `reconcile.py` pattern wholesale; no new abstraction layer, no new table, no new dependency.

No violations → Complexity Tracking left empty.

## Project Structure

### Documentation (this feature)

```text
specs/029-scrape-consistency-validation/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/           # Phase 1 output (alert payload contract)
└── tasks.md             # Phase 2 output (speckit tasks)
```

### Source Code (repository root)

```text
scripts/
├── scraper/
│   ├── consistency.py        # NEW — pure, stdlib-only: detect_inconsistencies + build_consistency_writeback
│   └── runner.py             # EDIT — call the check on the scrape-success path (after _reconcile_period);
│                             #        impure D1 prior-resolution read + atomic execute_sql + run-log warning
│                             #        + append mismatch to scrape_run["errors"]
└── tests/
    └── test_scrape_consistency.py   # NEW — unittest for the pure module (mirrors test_reconcile.py)
```

**Structure Decision**: Mirror the existing `reconcile.py` split exactly — a PURE module (`consistency.py`) that builds the discrepancy list + the alert dict + the one batched SQL string from already-fetched data and performs no I/O, plus the impure glue in `runner.py` (the prior-resolution `d1.query`, the single `d1.execute_sql`, the `logger.warning`, and the `scrape_run["errors"]` append). This keeps the scraper free of the analysis package (decoupling invariant) and keeps the detection logic unit-testable without `playwright`/D1.

## Complexity Tracking

> No constitution violations — section intentionally empty.
