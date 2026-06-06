# Quickstart: NF multi-entry reconciliation

**Feature**: 005-nf-multi-entry-reconciliation

## What changed

- Entries that share one Nota Fiscal (byte-identical document) are now **grouped** before amount validation.
- Amount validation reconciles **`sum(sibling amounts)` vs. the NF total** instead of comparing the full total to each entry → the false mismatches on split invoices are gone.
- Each unique shared NF is **vision-analyzed once** and reused across siblings.
- A **`duplicate_billing`** (critical) alert fires when siblings sum to **more** than the NF total (over-claim).

## Run the pipeline

```bash
# From repo root. Analyze documents (now dedups + reconciles groups):
python -m scraper analyze-docs            # or the existing doc-analysis subcommand

# Run the checks (now includes the duplicate-billing check; needs analyses present):
python -m scraper analyze                 # writes alerts into data/scrape/<period>.json

# Re-import into D1 (unchanged importer):
node scripts/import-to-d1.mjs             # local; or the prod import path
```

## Verify against the confirmed examples (`data/scrape/2025-12.json`)

- **NF-e 1057 quad** (administration 6.430,00 + assembly 452,00 + books 212,32 + tax-obligations 66,00 = **7.160,32**): all four siblings reconcile → none flagged `amount_match = 0`.
- **TPA internet pair** (internet 288,59 + JUROS/MULTAS 5,96 = **294,55**): both reconcile → not flagged.
- **VLM passes**: one per group (1 for the quad, not 4).

## Verify the over-claim alert (synthetic)

Construct a small fixture where two entries share one NF (gross total 100) but their amounts sum to 150, run `analyze`, and confirm exactly one `duplicate_billing` critical alert referencing both entries with `over_claim = 50`. A correctly-summing split produces none.

## Where it surfaces in the app

- **Document analyses** view: the split siblings show Amount = OK instead of mismatch (no UI change).
- **Alerts** view: the new `duplicate_billing` alert renders generically with its title/severity (no UI change).
