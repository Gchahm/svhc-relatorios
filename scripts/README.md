# Data Migration Scripts

Export data from the old PostgreSQL database and import into the new D1 database.

## Prerequisites

- Old PostgreSQL running (`cd ../fiscal-old && docker compose up -d`)
- [uv](https://github.com/astral-sh/uv) installed
- Local D1 migrations applied (`pnpm db:migrate:dev`)

## 1. Export from PostgreSQL

```bash
uv run --with psycopg2-binary scripts/export-old-db.py
```

This creates `data/export.json` with all tables mapped to the new schema.

Options:
- `-o <path>` — custom output path (default: `data/export.json`)
- `--database-url <url>` — custom PostgreSQL URL (default: `postgresql://fiscal:fiscal_dev@localhost:5432/fiscal`)

## 2. Import into D1

```bash
# Local
node scripts/import-to-d1.mjs

# Remote (production)
node scripts/import-to-d1.mjs --remote

# Generate SQL only (no execution)
node scripts/import-to-d1.mjs --dry-run
```

Options:
- `-i <path>` — custom input path (default: `data/export.json`)
- `--remote` — target remote D1 instead of local
- `--dry-run` — write `data/import.sql` without executing
