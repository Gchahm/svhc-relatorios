# Quickstart: Scraper and analysis directly on the database

After this feature, one command scrapes a period straight into D1 and R2; the analysis pipeline reads from there and writes results back. No `data/scrape/<period>.json` and no persistent image folder.

> Prereqs: `wrangler` authenticated (only for `--remote`); local D1 migrated (`pnpm db:migrate:dev`); `cd scripts && uv sync`. Run analysis/scrape from `scripts/` (the access layer invokes `wrangler` from the repo root automatically).

## Local end-to-end (default target)

```bash
# 1) Scrape a period straight into local D1 + upload images to local R2
cd scripts
uv run python -m scraper scrape --periodo 2025-12 --download-docs
#   → prints "target: local" and a per-table row summary; no period JSON written

# 2) Classify + analyze that period (reads D1, materializes images from R2, writes results to D1)
#    via the analyze-docs agent, or directly:
uv run python -m analysis docs-plan        --periodo 2025-12      # manifest + materialized images in .cache/analysis/2025-12/
uv run python -m analysis apply-extractions --periodo 2025-12     # upserts document_analyses to D1
uv run python -m analysis analyze          --periodo 2025-12      # upserts alerts to D1
uv run python -m analysis mismatches       --periodo 2025-12      # prints the summary (page_refs → cache images)

# 3) View in the app — images and analyses come from local D1/R2 already
cd .. && pnpm dev    # open the entries/analysis pages for 2025-12
```

## Against remote (production)

```bash
cd scripts
uv run python -m scraper scrape --periodo 2025-12 --download-docs --remote
#   → prints "target: REMOTE" BEFORE writing; relies on your wrangler auth

uv run python -m analysis apply-extractions --periodo 2025-12 --remote
uv run python -m analysis analyze          --periodo 2025-12 --remote
```

## Self-improving loop (unchanged UX, new plumbing)

```
/improve-classification run the classification improvement loop for 2025-12 [--remote]
```
The loop threads the target through analyze → review → fix; verdicts/manifest live in the ephemeral cache.

## What changed for you

- **Gone**: `node scripts/import-to-d1.mjs …` and `node scripts/upload-images-to-r2.mjs …` — folded into the scrape run.
- **Gone**: `data/scrape/<period>.json` and the persistent `data/scrape/<period>/` image folder.
- **New**: a `--remote` flag on scrape + analysis (default local); a git-ignored `.cache/analysis/<period>/` holding materialized images and per-run scratch (`.classify.json`, `.extract-todo.json`, `.verdicts.json`).
- **Same**: deterministic IDs, the D1 schema, what the analysis computes, and how the app reads data.

## Verify (parity)

For a period already imported via the old path, confirm the new analysis loader assembles the same in-memory data (counts + key values for entries/documents/analyses/alerts) — then a fresh `--download-docs` scrape + classify + analyze of a new period renders in the app identically to a JSON-era period.
