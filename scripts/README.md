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
