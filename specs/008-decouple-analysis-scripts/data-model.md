# Phase 1 Data Model: Decouple the Analysis Pipeline from the Scraper

This is a **behavior-preserving refactor** — there is **no data-model change**. No new entities, no
period-JSON or D1 schema change, no change to `document_analyses`/`analysis_records`/`alerts` or the
`mismatches` summary shape. The "model" here is the **module/package structure** and the contracts
that must stay invariant.

## Preserved contracts (must not change)

- **Period JSON** (`data/scrape/<period>.json`): the data shape scraper writes and analysis
  reads/augments. Unchanged.
- **`document_analyses` / `analysis_records` / `alerts`**: shapes produced by the analysis pipeline.
  Unchanged (the `import-to-d1.mjs` ingestion depends on them).
- **`det_id` / `NAMESPACE`**: `uuid5(NAMESPACE_DNS, "svhc.fiscal")` and `det_id(*parts)` semantics —
  byte-identical before and after; one shared implementation.
- **Working files**: `<period>.extract-todo.json` (manifest) and `<image>.classify.json` (per-page
  classification) — formats unchanged.
- **Analysis command surface**: `docs-plan`, `apply-extractions`, `analyze`, `mismatches` + their
  flags — see `contracts/analysis-cli.md`. Only the *entrypoint* (how they're invoked) moves.

## Module → package mapping (the actual change)

| Module today | After P3 | Depends on | Notes |
|--------------|----------|-----------|-------|
| `scraper/utils.py` (`det_id`, `NAMESPACE`, `now_ms`) | `common/` | stdlib | the only shared code; relocate verbatim |
| `scraper/runner.py`, `browser.py`, `config.py`, `extractors/` | `scraper/` | `common` + `playwright` | scraping; unchanged logic |
| `scraper/analise/{loader,models,documentos,nf_groups,extractions,reporter,checks}` | `analysis/` | `common` (stdlib) | analysis; intra-imports `..utils` → `common` |
| `scraper/__main__.py` (mixed CLI) | split: scraper CLI stays; analysis commands → `analysis` entrypoint | — | P1 lazy-imports runner; P2 moves analysis commands' entrypoint |

## Dependency direction (target)

```
        common  (det_id / NAMESPACE / now_ms — stdlib only)
        /     \
   scraper     analysis
 (+playwright) (stdlib only)
```

No cycles; `scraper` and `analysis` never import each other. The previous sole join point
(`__main__` importing both) is removed: scraping and analysis have separate entrypoints, each
importing only its own subtree + `common`.

## Staged states

- **P1**: structure unchanged; `__main__` lazy-imports `runner` so analysis commands don't pull
  Playwright.
- **P2**: analysis commands gain a dedicated entrypoint (console scripts + `python -m scraper.analise`
  dispatcher); still physically under `scraper/analise`.
- **P3**: the table above is realized — `common`/`scraper`/`analysis` packages in a uv workspace.
