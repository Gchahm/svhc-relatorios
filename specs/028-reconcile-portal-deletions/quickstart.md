# Quickstart: Reconcile Portal Deletions on Period Re-scrape

## What changed

A period re-scrape is now authoritative: rows removed from the brcondos portal are removed from the
D1 mirror (`entries`, `attachments`, `category_subtotals`, `approvers`), their analysis-owned
dependents are cascade-cleaned, and a `critical` `portal_row_vanished` alert records what
disappeared.

## Run it

```bash
cd scripts
# Re-scrape a specific period (explicit --periodo triggers a re-scrape of an already-present period)
uv run python -m scraper scrape --periodo 2026-01            # local D1
uv run python -m scraper scrape --periodo 2026-01 --remote   # production
```

On the scrape-success path for each period, reconciliation runs automatically. Look for the log line:

```
  Reconciled 2026-01: deleted entries=1 attachments=1 category_subtotals=0 approvers=0; alert raised
```

(or `nothing stale` when the mirror already matches the portal).

## Verify locally (no live portal needed)

Reconciliation is a pure diff over the just-scraped set vs. what's in D1, so you can exercise it by
simulating a portal deletion against local D1 data:

1. Confirm a period exists locally: `npx wrangler d1 execute DATABASE --local --command "SELECT
   period, COUNT(*) FROM accountability_reports r JOIN entries e ON e.report_id=r.id GROUP BY period"`.
2. Run the unit tests (the authoritative behavior check):
   `cd scripts && python -m unittest discover -s tests -t .` (or
   `python -m unittest discover -s scripts/tests -t scripts` from repo root).
3. UI check: after a reconcile that deletes a row, open `/dashboard/alerts` — a `critical`
   "ledger row(s) vanished from portal" alert appears for the period, and its affected-entry links
   point at the (now-removed) entries.

## Tests

```bash
cd scripts && python -m unittest discover -s tests -t .
```

`scripts/tests/test_reconcile.py` covers the no-op, stale diff, cascade, atomic-single-batch,
idempotent-alert-id, subtotals/approvers, surviving-rows-untouched, and SQL-escaping cases.
