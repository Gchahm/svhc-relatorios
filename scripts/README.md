# Scripts

All scripts output per-period JSON files to `data/scrape/` (one file per month, e.g. `2026-01.json`).
Reference data (categories, vendors, units, subcategories) uses deterministic UUIDs so the same
entity always gets the same ID across files — duplicates are safely ignored on import.

## Scraper

Scrapes accountability data from BRCondos portal.

### Setup

```bash
# Install playwright browser (one-time)
uv run --with playwright -- playwright install chromium
```

Requires env vars in `.env` at the project root:

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
uv run --with playwright --with python-dotenv -- python -m scraper scrape

# Scrape specific periods
uv run --with playwright --with python-dotenv -- python -m scraper scrape --periodo 2026-01 2025-12

# Also download document files
uv run --with playwright --with python-dotenv -- python -m scraper scrape --download-docs

# Custom output directory
uv run --with playwright --with python-dotenv -- python -m scraper scrape -o ../data/scrape
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
cd scripts && uv run --with playwright --with python-dotenv -- python -m scraper scrape && cd ..

# 2. Import into local D1
node scripts/import-to-d1.mjs

# 3. Import into production D1
node scripts/import-to-d1.mjs --remote
```
