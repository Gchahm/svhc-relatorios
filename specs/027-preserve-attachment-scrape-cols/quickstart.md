# Quickstart: Preserve scraper-owned attachment columns across re-scrapes

## What changed

The scraper no longer nulls `attachments.file_path` / `content_hash` when you re-scrape a period
without re-downloading images. Existing values survive; a successful re-download still overwrites.

## Run the unit tests

```bash
cd /home/agent/workspace/svhc-relatorios
python -m unittest discover -s scripts/tests -t scripts
```

Expect `test_attachment_preserve.py` (new) plus the existing suite to pass.

## Manual verification against local D1 (no portal login needed)

1. Inspect an attachment that already has a `file_path`/`content_hash` (or seed one):
   ```bash
   npx wrangler d1 execute fiscal-db --local --command \
     "SELECT id, file_path, content_hash FROM attachments WHERE file_path IS NOT NULL LIMIT 3"
   ```
2. Simulate the re-scrape merge with the pure helper (Python REPL or a one-off script): build a fresh
   row dict with the same `id` but `file_path=None, content_hash=None`, read the existing map via
   `d1.query(...)`, call `_preserve_existing_attachment_cols`, upsert, and re-query — the values must
   be unchanged.
3. Confirm `attachment_state` for those attachment ids is unchanged before/after:
   ```bash
   npx wrangler d1 execute fiscal-db --local --command \
     "SELECT attachment_id, classified_at FROM attachment_state LIMIT 5"
   ```

## Lint / format before commit

```bash
pnpm lint && pnpm format
```
(TypeScript is untouched, but the gates still run per the constitution.)
