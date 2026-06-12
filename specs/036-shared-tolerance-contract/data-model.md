# Phase 1 Data Model: Shared reconciliation tolerance/status contract

No persisted entities, no D1 schema, no migration. The only "data" is the test-only fixture.

## Entity: Reconciliation contract case (fixture record)

A single case in `scripts/analysis/reconciliation_contract.json`.

| Field    | Type                                   | Notes |
|----------|----------------------------------------|-------|
| `name`   | string                                 | Human-readable case id (unique within the fixture). |
| `sum`    | number                                 | The sibling/entry-amount sum (TS `sumEntries`, Python `sibling_sum`). |
| `total`  | number \| null                         | The NF/document total (TS `totalValue`, Python `nf_total`). `null` models a missing total. |
| `status` | enum `within` \| `over` \| `under` \| `unknown` | Canonical expected reconciliation status. |

### Validation rules

- `status` ∈ {`within`, `over`, `under`, `unknown`} (both tests assert membership implicitly
  by comparing against the function output mapped to this vocabulary).
- A `null` or `<= 0` `total` MUST map to `status: "unknown"`.
- Otherwise `status` follows the band: `within` iff `|sum-total| <= 0.05` OR
  `|sum-total|/total < 0.05`; else `over` iff `sum > total`, else `under`.

### Fixture file shape

```json
{
  "notes": "Canonical (sum,total)->status contract shared by Python nf_groups.reconcile_group and TS documentStatus. Status names are TS-flavored; Python maps reconciled->within, over_claim->over, under_claim->under, None->unknown.",
  "cases": [
    { "name": "exact_match", "sum": 100.0, "total": 100.0, "status": "within" }
  ]
}
```

## Status-name equivalence (canonical ↔ Python)

| Canonical (fixture / TS) | Python `reconcile_group` |
|--------------------------|--------------------------|
| `within`                 | `"reconciled"`           |
| `over`                   | `"over_claim"`           |
| `under`                  | `"under_claim"`          |
| `unknown`                | `None`                   |

This table is the contract both tests encode; it is the only place the two vocabularies meet.
