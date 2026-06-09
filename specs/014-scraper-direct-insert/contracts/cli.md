# Contract: CLI command surfaces (scraper + analysis)

A single `--remote` flag (default = local) is added across the scrape and analysis commands; every command that touches data threads it to `scripts/common/d1.py`. No period JSON is read or written anywhere.

## Scraper — `scripts/scraper/__main__.py`

### `scrape`
| Flag | Before | After |
|------|--------|-------|
| `--periodo <YYYY-MM …>` | unchanged | unchanged |
| `--book-ids <int …>` | unchanged | unchanged |
| `--download-docs` | saves images to `data/scrape/<period>/` | uploads images to R2 (`<period>/<basename>`) during the run |
| `--output-dir/-o` | dir for period JSON | **removed** (no JSON resting place) |
| `--remote` | — | **new**; absent ⇒ local D1/R2, present ⇒ remote |
| `--cache-dir` | — | **new, optional**; ephemeral local scratch for the run (default `.cache/analysis`) |

**Behavior**: builds the in-memory `period_data` exactly as today, then `upsert_tables(period_data, target=...)` instead of `write_text`. Prints the resolved target and a per-table row summary (FR-005). On failure, reports and leaves prior state (FR-007); re-run heals (FR-006). When `--download-docs`, each page is uploaded to R2 and `documents.file_path` is set to the `;`-joined `<period>/<basename>` key form.

### `download-docs`
- Repurposed (or merged into `scrape --download-docs`): for documents in D1 whose images are not yet in R2, download and upload them, updating `documents.file_path` in D1.
- Gains `--remote`; `--data-dir` (the old JSON dir) is removed/replaced by D1 scoping.

## Analysis — `scripts/analysis/__main__.py`

Every command gains `--remote` (default local) and an optional `--cache-dir`. `--data-dir` (the JSON location) is removed; periods are scoped via D1.

| Command | Reads (new) | Writes (new) |
|---------|-------------|--------------|
| `docs-plan` | D1 (period rows) + R2 (materialized images for grouping) | `<period>.extract-todo.json` in the **cache dir**; `read_path`s point at materialized cache images |
| `apply-extractions` | manifest + `<image>.classify.json` (cache) + D1 (period) | **D1**: upsert `document_analyses` + `document_analysis_records` |
| `analyze` | D1 (period, incl. analyses) | **D1**: upsert `alerts` |
| `mismatches` | D1 (period) | stdout JSON (unchanged); `page_refs[].read_path` points at materialized cache images |
| `record-verdict` | `<period>.verdicts.json` (cache) | `<period>.verdicts.json` (cache) |
| `loop-state` | `<period>.verdicts.json` (cache) + D1 (via `summarize_mismatches`) | `<period>.verdicts.json` (cache) |

**Invariant**: the in-memory `PeriodData`/`raw` shape returned by `load_all_periods` is identical to today (see data-model.md), so `analyze`, all `checks/*`, `select_work`, `summarize_mismatches`, `nf_groups`, and `loop_state` are unchanged in logic.

## Skills & agents (pass the target through)

- **classify-doc-page**: unchanged behavior — Reads the image path it is given (now a cache path) and writes the sibling `.classify.json` (now in the cache dir).
- **classify-period**: runs `docs-plan` (which materializes images), fans out `classify-doc-page` over the manifest `read_path`s; carries `--remote`/scope.
- **analyze-docs agent**: `classify-period` → `apply-extractions` → `analyze` → `mismatches`, all with the target flag; returns the same terse summary.
- **review-mismatch agent**: opens `page_refs[].read_path` (cache image) with Read; reads the ledger entry via `mismatches --document-id` (now D1-backed).
- **fix-mismatch agent**: scoped verify commands (`docs-plan`/`apply-extractions`/`analyze`/`mismatches`) carry the target flag.
- **improve-classification skill**: threads `--remote` through analyze/review/fix and the `loop-state`/`record-verdict` calls.

## Removed

- `scripts/import-to-d1.mjs` and `scripts/upload-images-to-r2.mjs` (logic folded into `scripts/common/d1.py` + the scrape run).
- The period JSON (`data/scrape/<period>.json`) and the persistent `data/scrape/<period>/` image folder as sources of truth.
