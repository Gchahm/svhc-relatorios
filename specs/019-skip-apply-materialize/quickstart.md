# Quickstart & Verification: Skip R2 image materialization in apply-extractions

**Feature**: 019-skip-apply-materialize | **Date**: 2026-06-10

## What changed

`apply-extractions` no longer downloads page images from R2 on every run. It now materializes only
the attachments that actually need a `content_hash` backfill (page-bearing **and** missing a hash).
When every page-bearing attachment is already keyed (the normal case after feature 021), the apply
step makes **zero** R2 image reads. The classify (`docs-plan`) and review (`mismatches`) steps are
unchanged and still materialize their images.

## Run it

```bash
cd scripts
uv run python -m analysis apply-extractions --periodo 2025-12   # local
# add --remote for production
```

## Verify (acceptance)

### SC-001 / FR-001 — no downloads in the steady state

On a DB where every page-bearing attachment has a `content_hash`:

```bash
# Confirm the DB is fully keyed (expect 0 page-bearing rows without a hash):
uv run python -m analysis ... # or:
wrangler d1 execute fiscal-db --local --command \
  "SELECT count(*) FROM attachments WHERE content_hash IS NULL AND file_path IS NOT NULL AND file_path != '';"
# → 0

uv run python -m analysis apply-extractions --periodo 2025-12
```

**Expect**: a log line like `All page-bearing attachments already have content_hash; skipping R2
image materialization`, and **no** `Materialized N page image(s) from R2` line.

### SC-002 / FR-005 — output parity

```bash
# Snapshot the persisted analyses before:
wrangler d1 execute fiscal-db --local --command \
  "SELECT attachment_id, amount_match, vendor_match, date_match FROM attachment_analyses ORDER BY attachment_id;" > /tmp/before.txt

# Mark the period pending and re-apply (with the change in place):
uv run python -m analysis mark-pending --entry-id ...   # or re-run a fresh classify+apply
uv run python -m analysis apply-extractions --periodo 2025-12

wrangler d1 execute fiscal-db --local --command \
  "SELECT attachment_id, amount_match, vendor_match, date_match FROM attachment_analyses ORDER BY attachment_id;" > /tmp/after.txt

diff /tmp/before.txt /tmp/after.txt   # → no differences
```

### SC-003 / FR-002 — legacy backfill still works

```bash
# Clear the hash on one page-bearing attachment:
wrangler d1 execute fiscal-db --local --command \
  "UPDATE attachments SET content_hash = NULL WHERE id = '<some-page-bearing-id>';"

uv run python -m analysis apply-extractions --periodo 2025-12
```

**Expect**: a `Materialized N page image(s) from R2` line (only that attachment's pages) and a
`Backfilled content_hash for 1 attachment(s)` line; afterwards:

```bash
wrangler d1 execute fiscal-db --local --command \
  "SELECT content_hash FROM attachments WHERE id = '<some-page-bearing-id>';"
# → non-NULL again
```

### FR-004 — page-less attachment is not work

A `content_hash IS NULL` row whose `file_path` is empty must NOT cause a download:

```bash
# With all page-bearing rows keyed but a page-less row having NULL hash, apply still logs the skip.
uv run python -m analysis apply-extractions --periodo 2025-12   # → skip line, no downloads
```

### FR-006 — classify/review still materialize

```bash
uv run python -m analysis docs-plan --periodo 2025-12   # still emits Materialized … (images present for vision)
uv run python -m analysis mismatches --periodo 2025-12  # page_refs read_paths still point at cache files
```

## Pre-commit gates

```bash
pnpm lint
pnpm format
```
