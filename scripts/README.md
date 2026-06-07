# Scripts

All scripts output per-period JSON files to `data/scrape/` (one file per month, e.g. `2026-01.json`).
All entities use deterministic UUIDs — the same data always produces the same IDs, so re-scraping
a period safely upserts via `INSERT OR REPLACE`.

## Scraper

Scrapes accountability data from BRCondos portal.

### Setup

```bash
cd scripts

# Install dependencies
uv sync

# Install playwright browser (one-time)
uv run playwright install chromium
```

Requires env vars in `scripts/.env`:

```
BRCONDOS_URL=https://ssl.brcondos.com.br
BRCONDOS_USER=...
BRCONDOS_PASSWORD=...
HEADLESS=true
```

### Usage

```bash
cd scripts

# Scrape all new periods (skips those with existing JSON files)
uv run python -m scraper scrape

# Scrape specific periods
uv run python -m scraper scrape --periodo 2026-01 2025-12

# Also download document files
uv run python -m scraper scrape --download-docs

# Download documents for already-scraped periods (updates JSON in-place)
uv run python -m scraper download-docs
uv run python -m scraper download-docs --periodo 2024-12
```

## Document analysis

Turns the downloaded document page images into structured records, validates them against the
ledger, and surfaces mismatches / fraud signals. It writes everything back into the same period
JSON. The flow is five steps:

```
scrape / download-docs  →  [1] docs-plan  →  [2] classify  →  [3] apply-extractions  →  [4] analyze  →  [5] mismatches
```

Steps 1, 3, 4 and 5 are deterministic CLI commands (stdlib only, no browser). Step 2 is the only
vision step and runs inside Claude Code via skills/agent — the old local VLM (`mlx_vlm`) is retired.

### 1. `docs-plan` — pick the work and group shared invoices

```bash
cd scripts
uv run python -m analysis docs-plan --periodo 2025-12 [--document-id <ids…>] [--entry-id <ids…>]
```

Reads the period JSON, selects the documents to analyze (a whole period, or just the documents/
entries you name), and groups **byte-identical Nota Fiscal copies** so each unique invoice is read
only once. Writes the work manifest `data/scrape/<period>.extract-todo.json` — the representative
page images to read plus the ledger context for reconciliation. Targeting specific ids re-plans
those even if already analyzed.

### 2. `classify` — read each page image into structured fields (vision)

Inside Claude Code, invoke the **`classify-period`** skill for a period (or subset). It runs
`docs-plan` itself, then fans each representative page out to the **`classify-doc-page`** skill,
which views one image and writes `<image>.classify.json` next to it (gross / net / paid amounts,
CNPJ, issuer, date, document number, service, and the artifact role). The **`analyze-docs` agent**
wraps this whole analysis in an isolated context and hands a caller back only the summary (step 5).
This is the only non-deterministic step.

### 3. `apply-extractions` — merge classifications into the ledger data

```bash
cd scripts
uv run python -m analysis apply-extractions --periodo 2025-12
```

Reads each page's `.classify.json`, rolls each document up (heterogeneity-aware: a document bundling
an invoice, a boleto, and a payment proof resolves to one amount by precedence), reconciles shared-NF
groups (sum of sibling entries vs. the NF total), fans the result out to the sibling entries,
validates amount / vendor / date against the ledger entry, and writes `document_analyses` (with
per-page `analysis_records`) into the period JSON.

### 4. `analyze` — run the checks

```bash
cd scripts
uv run python -m analysis analyze --periodo 2025-12
```

Runs the financial / consistency / fraud checks over the period JSON and writes `alerts` — e.g.
`duplicate_billing` when one Nota Fiscal is claimed above its face value, vendor concentration, new
vendors, delinquency, etc.

### 5. `mismatches` — terse summary of what disagrees

```bash
cd scripts
uv run python -m analysis mismatches --periodo 2025-12 [--document-id <ids…>] [--entry-id <ids…>]
```

Prints a compact JSON list of classification mismatches — `amount` / `vendor` / `date` /
`page-error` / `duplicate_billing` — each joined with the ledger-vs-extracted values. Read-only (no
writes). This is exactly what the `analyze-docs` agent returns to its caller.

The `.extract-todo.json` and `.classify.json` files are intermediate working artifacts (gitignored);
the period JSON (`data/scrape/<period>.json`) is the source of truth and the final destination.

## Import into D1

Reads all JSON files from a directory (or a single file) and imports into D1.

```bash
# Local (reads all files from data/scrape/)
node scripts/import-to-d1.mjs

# Remote (production)
node scripts/import-to-d1.mjs --remote

# Single file
node scripts/import-to-d1.mjs -i data/scrape/2026-01.json

# Generate SQL only (no execution)
node scripts/import-to-d1.mjs --dry-run
```

## Typical workflow

```bash
# 1. Scrape
cd scripts && uv run python -m scraper scrape && cd ..

# 2. Import into local D1
node scripts/import-to-d1.mjs

# 3. Import into production D1
node scripts/import-to-d1.mjs --remote

# 4. Download documents (optional, can be done later)
cd scripts && uv run python -m scraper download-docs && cd ..
node scripts/import-to-d1.mjs --remote  # re-import to update file_path
```

### With document analysis

```bash
cd scripts

# 1. Plan + classify the documents (steps 1-2). In Claude Code, invoke the
#    classify-period skill for the period; it runs docs-plan and writes the
#    per-page <image>.classify.json files. (Or analyze a subset with --document-id.)

# 2. Merge classifications, run checks, get the summary (steps 3-5)
uv run python -m analysis apply-extractions --periodo 2025-12
uv run python -m analysis analyze --periodo 2025-12
uv run python -m analysis mismatches --periodo 2025-12

cd ..
# 3. Push document_analyses + alerts into D1
node scripts/import-to-d1.mjs
```
