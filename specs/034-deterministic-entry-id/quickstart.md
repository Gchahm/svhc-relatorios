# Quickstart: Deterministic Entry IDs for Duplicate Natural Keys

## What changed

Entry ids are now derived so that duplicate ledger lines sharing a natural key are disambiguated
by an **order-independent portal-native discriminator** (their document ids) when possible,
instead of the order the rows appeared in the portal. Unique entries' ids are unchanged.

## Run the unit tests

```bash
cd scripts
python -m unittest discover -s tests -t .
# or from repo root:
python -m unittest discover -s scripts/tests -t scripts
```

`test_entry_ids.py` asserts: order-independence for distinct-doc duplicates, no id churn for
singletons (id == legacy `det_id(...,'1')`), fallback notes for no-doc duplicates (and none for
doc-distinguished groups), within-group uniqueness, and drift detection.

## Verify against local data

The local D1 contains a real instance: three identical `ENERGIA ELÉTRICA` charges (2026-01) with
distinct doc ids 18990374/375/376.

```bash
cd scripts
python3 - <<'PY'
from scraper.entry_ids import assign_entry_ids, EntryKeyInput
period = "2026-01"
sub = "5d1ae03c-7f83-5f1a-8726-90df7aa489ea"
rows = [
    EntryKeyInput("2026-01-20", "ENERGIA ELÉTRICA - ENERGIA ELÉTRICA", 101.76, sub, [18990374]),
    EntryKeyInput("2026-01-20", "ENERGIA ELÉTRICA - ENERGIA ELÉTRICA", 101.76, sub, [18990375]),
    EntryKeyInput("2026-01-20", "ENERGIA ELÉTRICA - ENERGIA ELÉTRICA", 101.76, sub, [18990376]),
]
a = assign_entry_ids(period, rows)
ids_fwd = [x.entry_id for x in a.assigned]
b = assign_entry_ids(period, list(reversed(rows)))
# map id by doc to compare order-independence
by_doc_fwd = {r.documento_ids[0]: x.entry_id for r, x in zip(rows, a.assigned)}
by_doc_rev = {r.documento_ids[0]: x.entry_id for r, x in zip(reversed(rows), b.assigned)}
assert by_doc_fwd == by_doc_rev, "ids must be stable across reorder"
print("order-independent OK:", by_doc_fwd)
print("fallback notes (should be empty):", a.fallback_notes)
PY
```

## End-to-end (optional, requires portal creds)

```bash
cd scripts
uv run python -m scraper scrape --periodos 2026-01 --download-docs   # local D1
```

Re-running the same period twice yields identical ids for the ENERGIA ELÉTRICA group. Any
no-doc duplicate group (e.g. the BLOCO C receipts) produces a fallback note in the run log /
`scrape_runs.errors`.
