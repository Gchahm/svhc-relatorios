# Quickstart: Prune consumed and stale `page_classifications` staging rows

## What changed

The `page_classifications` staging table is now self-cleaning:

- `apply-extractions` deletes an attachment's staging rows once its authoritative
  `attachment_analyses` write lands (atomically, in the same batch).
- `mark-pending` deletes a re-queued attachment's staging rows so reclassification starts clean.

No schema/migration change; no new CLI command; no mirror-table write.

## Run the unit tests

```bash
cd /home/agent/workspace/svhc-relatorios
python -m unittest discover -s scripts/tests -t scripts
```

Expect `test_prune_staging.py` to pass (helper output + batch composition for both hooks), and all
pre-existing tests to remain green.

## Verify against local D1 (prod-like data)

```bash
cd /home/agent/workspace/svhc-relatorios

# 1) Pick a period that has classified attachments, and count its staging rows before/after.
npx wrangler d1 execute fiscal-db --local \
  --command "SELECT COUNT(*) AS n FROM page_classifications;"

# 2) Re-queue one attachment and confirm its staging rows are cleared.
python -m analysis mark-pending --attachment-id <ATTACHMENT_ID>
npx wrangler d1 execute fiscal-db --local \
  --command "SELECT COUNT(*) AS n FROM page_classifications WHERE attachment_id = '<ATTACHMENT_ID>';"
# -> n = 0

# 3) (Optional, end-to-end) classify + apply that attachment, then confirm its staging rows are
#    gone while its attachment_analyses row exists:
python -m analysis apply-extractions --periodo <YYYY-MM>
npx wrangler d1 execute fiscal-db --local \
  --command "SELECT
       (SELECT COUNT(*) FROM page_classifications WHERE attachment_id='<ATTACHMENT_ID>') AS staging,
       (SELECT COUNT(*) FROM attachment_analyses   WHERE attachment_id='<ATTACHMENT_ID>') AS analysis;"
# -> staging = 0, analysis = 1
```

## Files touched

- `scripts/analysis/page_classifications.py` — new `_prune_page_classifications_sql` helper.
- `scripts/analysis/attachments.py` — `_merge_and_write` folds the prune DELETE into its atomic batch.
- `scripts/analysis/extractions.py` — `mark_pending` folds the prune DELETE into its batch.
- `scripts/tests/test_prune_staging.py` — unit tests.
