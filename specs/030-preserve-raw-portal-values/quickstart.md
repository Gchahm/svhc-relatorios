# Quickstart: Preserve Raw Portal Values on Mirror Rows

## What changed

- `entries` mirror rows now carry `raw_amount` and `raw_description` — the verbatim portal cell text
  for the amount and the (pre-normalization) description.
- `parse_brl` no longer aborts a period on a malformed amount cell: the bad ledger row is skipped with
  a logged warning, and the skip is recorded on the scrape run's notes.

## Apply the migration (local)

```bash
# Generate (if regenerating) — pnpm db:generate fails in-sandbox; call the binary directly:
node_modules/.bin/drizzle-kit generate
# Apply to local D1:
pnpm db:migrate:dev      # or: node_modules/.bin/wrangler d1 migrations apply fiscal-db --local
```

## Re-scrape a period to populate raw provenance

```bash
# Local D1 (default). Re-scrape an explicit period so its rows get the new columns:
uv run python -m scraper scrape --periodo 2026-01 --download-docs
```

## Verify from D1

```bash
node_modules/.bin/wrangler d1 execute fiscal-db --local --json \
  --command "SELECT id, amount, raw_amount, substr(description,1,30) AS description, substr(raw_description,1,40) AS raw_description FROM entries WHERE raw_amount IS NOT NULL LIMIT 5"
```

Expect: every re-scraped row has a non-null `raw_amount` whose parse equals `amount`, and a non-null
`raw_description`.

## Run the parser unit tests

```bash
python -m unittest discover -s scripts/tests -t scripts
```

## Quality gates before commit

```bash
pnpm lint
pnpm format
```
