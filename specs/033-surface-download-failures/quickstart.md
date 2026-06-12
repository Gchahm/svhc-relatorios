# Quickstart: Surface partial attachment-download failures

## Run the unit tests (pure helpers + analysis check)

```bash
cd scripts
python -m unittest discover -s tests -t scripts
```

Expected: the new `test_download_failures.py` and `test_attachment_not_downloaded.py` pass alongside
the existing suite.

## Verify the run-level signal (operability) against local D1

A real partial download needs a flaky portal, so verify the *signal* deterministically:

1. In local D1, find an attachment with `file_path IS NULL` (or null one out for a known period):
   ```bash
   npx wrangler d1 execute fiscal-db --local --command \
     "SELECT d.id, r.period FROM attachments d JOIN entries e ON d.entry_id=e.id \
      JOIN accountability_reports r ON e.report_id=r.id WHERE d.file_path IS NULL LIMIT 5;"
   ```
2. Run the analysis pass for that period and confirm the alert appears:
   ```bash
   cd scripts && uv run python -m analysis analyze --periodo <YYYY-MM>
   npx wrangler d1 execute fiscal-db --local --command \
     "SELECT id, type, reference_period FROM alerts WHERE type='attachment_not_downloaded';"
   ```
3. Re-run `analyze` and confirm the count is unchanged (idempotent).
4. Set a `file_path` on the attachment, re-run `analyze`, and confirm its alert is gone (self-clears).

## Verify the alert on the dashboard (auditor surface)

Log in (`ui-login` skill), open `/dashboard/alerts`, filter/scan for the
`attachment_not_downloaded` alert; click its affected-entry deep link and confirm it lands on
`/dashboard/entries?period=<YYYY-MM>&entry=<entryId>`.

## Status precedence (unit-verified)

`resolve_status(has_fatal_errors, any_download_failed)`:
- `(False, False) -> "success"`
- `(False, True)  -> "partial"`
- `(True,  *)     -> "error"`
