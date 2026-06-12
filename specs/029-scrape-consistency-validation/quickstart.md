# Quickstart: Scrape-time consistency validation

## What it does

When a period is (re-)scraped successfully, the scraper cross-checks the period's own three views of the money and, if they don't add up beyond rounding, raises a `scrape_inconsistency` `warning` alert, logs a warning, and notes it on the scrape run.

## Run / verify locally

The detection is exercised by the scraper's success path. Because a live brcondos scrape can't run in the sandbox, verify via:

### 1. Unit tests (pure module)

```bash
cd /home/agent/workspace/svhc-relatorios
python -m unittest discover -s scripts/tests -t scripts
```

Covers: consistent period → no alert (lone DELETE); dropped-entry subcategory mismatch → discrepancy + INSERT; demonstrativo C/D mismatch → discrepancy; sub-tolerance rounding → no alert; resolution graft; affected_entry_ids population; one-sided key (entries but no subtotal) → discrepancy.

### 2. Cross-check against the local prod-like D1 (false-alarm guard, SC-002)

A small read-only script reproduces the check over every period already in local D1 (entries + category_subtotals + accountability_reports) and prints any period that would fire — expected: none (or only genuinely inconsistent historical periods). Run:

```bash
python -m scripts.tests.consistency_against_local_d1   # ad-hoc verification helper (see PR notes)
```

(Implemented as a one-off verification snippet during the PR phase; the durable test is the unittest file.)

### 3. Dashboard

A fired alert appears at `/dashboard/alerts` as a `scrape_inconsistency` (warning) with the disagreeing numbers in its detail and deep links to any affected entries — no UI change needed (the alerts surface renders any type generically).

## Key invariants preserved

- No mirror-table write (entries/attachments/category_subtotals/approvers/accountability_reports untouched).
- No schema migration.
- Scraper does not import the analysis package.
- Writeback is one atomic D1 batch; idempotent per period; operator resolution/notes preserved across re-scrapes.
