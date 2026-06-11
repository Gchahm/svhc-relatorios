# Quickstart: Analysis-owned attachment state table

## What changed (operator view)

Classification state (`classified_at`) moved from the mirror table `attachments` to a new
analysis-owned table `attachment_state`. The analysis pipeline no longer writes `attachments`
at all (the `content_hash` backfill was removed; `content_hash` is now scraper-only). The
classification loop CLIs behave identically.

## Apply the migration (local)

```bash
# Generate the schema migration after editing src/db/fiscal.schema.ts:
node_modules/.bin/drizzle-kit generate     # (pnpm db:generate; use .bin directly if the pnpm shim fails)
# Hand-augment the generated drizzle/0012_*.sql to copy classified_at BEFORE dropping the column
# (see data-model.md "Migration data flow"), then:
pnpm db:migrate:dev                         # apply to local D1
```

## Verify the pipeline still works (local D1)

```bash
# 1. Pending set after migration: previously-classified attachments stay classified.
uv run python -m analysis docs-plan --periodo <YYYY-MM>      # expect: only un-classified attachments listed

# 2. Re-queue one, confirm it returns to pending:
uv run python -m analysis mark-pending --attachment-id <id>
uv run python -m analysis docs-plan --periodo <YYYY-MM>      # expect: <id> now listed pending

# 3. Full loop still classifies + stamps state:
uv run python -m analysis apply-extractions --periodo <YYYY-MM>
sqlite3 .wrangler/.../fiscal-db.sqlite \
  "SELECT count(*) FROM attachment_state WHERE classified_at IS NOT NULL;"   # > 0

# 4. The invariant: analysis wrote NOTHING to attachments.
#    Snapshot attachments before a run, run apply/analyze, diff — expect zero pipeline-attributable rows.
```

## Run the tests

```bash
python -m unittest discover -s scripts/tests -t scripts
```

## Verify the UI is unaffected (running app)

`classified_at` / `content_hash` are analysis-internal — no API route or dashboard reads them.
Log in (`ui-login`) and confirm `/dashboard/documents`, `/dashboard/entries`, and the attachment
analysis detail dialog still render against the migrated local D1.

## Known follow-up (out of scope)

A legacy attachment with `file_path` set but `content_hash IS NULL` (scraped pre-016, never
re-downloaded) is grouped correctly via the in-memory hash fallback per run, but its
`content_hash` column stays NULL until the scraper re-downloads its images. Persisting that hash
is a scraper enhancement (the scraper's `run_download_docs` only revisits `file_path IS NULL`
rows today), intentionally not done here to keep the invariant clean.
