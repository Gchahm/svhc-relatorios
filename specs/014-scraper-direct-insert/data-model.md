# Phase 1 Data Model: Scraper and analysis operate directly on the database

This feature **changes where data lives and how it is read/written, not what it is**. The D1 schema (Drizzle), table names, columns, and deterministic IDs are unchanged. This document captures the entities as they pertain to the new data flow, the in-memory shape the analysis pipeline depends on, and the two contracts that must stay in sync.

## Persisted entities (Cloudflare D1 — schema unchanged)

These are the tables the scraper now upserts directly and the analysis pipeline reads/writes, in `TABLE_ORDER` (FK-safe):

| Table | Written by (new) | Read by (new) | Notes |
|-------|------------------|---------------|-------|
| `scrape_runs` | scraper → D1 | — | run metadata; `id` is the only non-deterministic id |
| `categories` | scraper → D1 | analysis loader | deterministic id (`det_id("category", name)`) |
| `vendors` | scraper → D1 | analysis loader | `det_id("vendor", name)`; vendor-first-seen logic preserved |
| `units` | scraper → D1 | analysis loader | `det_id("unit", code)` |
| `subcategories` | scraper → D1 | analysis loader | `det_id("subcategory", category_id, name)` |
| `accountability_reports` | scraper → D1 | analysis loader | one per period; loader keys periods off this |
| `entries` | scraper → D1 | analysis loader | ledger line items; `amount`, `vendor_id`, `external_document_id` |
| `category_subtotals` | scraper → D1 | analysis loader | aggregates |
| `approvers` | scraper → D1 | analysis loader | approval chain |
| `documents` | scraper → D1 | analysis loader + frontend | **`file_path` now holds R2-key-form tokens** (see contract below) |
| `document_analyses` | **analysis → D1** (was JSON) | analysis + frontend | roll-up; empty at scrape time |
| `document_analysis_records` | **analysis → D1** (was nested JSON) | analysis + frontend | flattened from `analysis_records`; one per page |
| `alerts` | **analysis → D1** (was JSON) | analysis + frontend | check findings; empty at scrape time |

**Upsert semantics**: ledger writes use `INSERT OR REPLACE` keyed on `id` — re-scraping overwrites in place with no duplicates (FR-006, SC-004); deterministic IDs (`scripts/common/__init__.py:det_id`) are unchanged, so a re-run reproduces identical keys. **Analysis writebacks (`document_analyses`/`document_analysis_records`, `alerts`) use delete-then-insert** (a scoped `DELETE` via `execute_sql`, then `upsert_tables`) so a re-analysis that produces fewer pages, a different NF grouping, or fewer alerts cannot leave orphaned rows behind (see `contracts/period-loader-and-writeback.md`).

**At scrape time**: `document_analyses`, `document_analysis_records`, and `alerts` are left empty/untouched for the period (FR-009) — the scraper writes the ten ledger tables; analysis fills the other three later.

## Object storage entity (Cloudflare R2 — `fiscal-documents`, unchanged)

| Object | Written by (new) | Read by (new) |
|--------|------------------|----------------|
| Page image at key `<period>/<basename>` | scraper → R2 during the run | frontend (`/api/document-analyses/[id]/image/[page]`) + analysis materialization |

Content-Type set on put (`image/png` / `image/jpeg`). Same idempotent-overwrite behavior as `upload-images-to-r2.mjs`.

## In-memory shape the analysis pipeline depends on (must be preserved)

`loader.py:load_all_periods(...)` currently returns `(dict[str, PeriodData], RefIndex)` built from JSON files. After the change it builds the **same** structures from D1 queries. Every downstream consumer reads these fields, so the loader's output contract is frozen:

```
PeriodData:
  period: str                       # = accountability_reports[].period
  raw: dict                         # the full per-period dict, same keys as the old <period>.json:
                                    #   scrape_runs, categories, vendors, units, subcategories,
                                    #   accountability_reports, entries, category_subtotals,
                                    #   approvers, documents, document_analyses, alerts
                                    #   (document_analyses[].analysis_records rebuilt from
                                    #    document_analysis_records rows so callers that read the
                                    #    nested array keep working)
  report: dict                      # raw["accountability_reports"][0]
  entries: list[dict]               # raw["entries"]
  category_subtotals: list[dict]
  documents: list[dict]             # raw["documents"] (file_path = R2-key tokens)
RefIndex:                           # merged reference index incl. vendor_first_seen across all periods
```

**Consumers that must keep working unchanged** (they read in-memory `PeriodData`, not files): `run_all_checks` and all `checks/*.py`, `check_duplicate_billing` (`period.raw["document_analyses"]`), `select_work`, `summarize_mismatches`, `nf_groups.group_documents`, `loop_state`. Rebuilding `raw` with the identical key set is the core invariant of slice 4.

## Ephemeral working artifacts (local scratch, not a source of truth)

Live under a git-ignored cache dir (default `.cache/analysis/<period>/`), regenerated from D1+R2:

| Artifact | Producer | Consumer | Status |
|----------|----------|----------|--------|
| Materialized page image (`<period>/<basename>` fetched from R2) | `analysis/images.py` | `classify-doc-page` (vision Read), `nf_groups.content_hash` | ephemeral; deleted/overwritable |
| `<image>.classify.json` | `classify-doc-page` skill | `FileExtractionProvider` (apply-extractions) | ephemeral; raw per-page vision output |
| `<period>.extract-todo.json` | `docs-plan` | `apply-extractions`, `classify-period` | ephemeral manifest; `read_path` → cache image |
| `<period>.verdicts.json` | `record-verdict`/`loop-state` | the improve-classification loop | ephemeral loop bookkeeping |

These are intra-run coordination only — never the hand-off that gets data *into* the database (that hand-off is now direct D1 upsert).

## Contract A — `documents.file_path` ↔ R2 object key (must stay in sync)

- Scraper writes `file_path` = `";".join("<period>/<basename>")` for each page, and uploads each page to R2 at key `<period>/<basename>`.
- Frontend `src/lib/r2.ts:objectKeyFromFilePath(segment)` returns `<period>/<basename>` for these tokens unchanged (no `data/scrape/` marker present), and still strips legacy `…/data/scrape/<period>/<basename>` forms — so old and new rows both resolve.
- Analysis materialization uses each `file_path` token directly as the R2 `get` key.
- `parsePage` continues to derive `pageLabel`/`pageIndex` from the basename (`_p<n>.<ext>`), so `/pages` and `/image/[page]` routes are unaffected.

## Contract B — D1 row dicts ↔ generated SQL

- Python SQL generation derives columns from `Object.keys(row)` equivalents (the row dict), so the persisted columns are exactly whatever the scraper/analysis put in the dict — identical to today's `import-to-d1.mjs` behavior. The Drizzle schema remains the source of truth for column existence; the generator never hardcodes a column list.
- `document_analyses[].analysis_records` (nested) is flattened into `document_analysis_records` rows on write, and re-nested on read (loader), preserving both the persisted normalized form and the in-memory shape callers expect.

## State transitions (per period)

```
(absent) --scrape--> ledger tables populated in D1; images in R2; analyses/alerts empty
        --classify+apply-extractions--> document_analyses + document_analysis_records populated in D1
        --analyze--> alerts populated in D1
        --(improve loop)--> verdicts (scratch) drive scoped re-runs; analyses/alerts updated in D1
        --re-scrape (any time)--> ledger tables overwritten in place (idempotent); analyses/alerts left as-is unless re-run
```
