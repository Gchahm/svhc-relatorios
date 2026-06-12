# Contract: reconciliation_contract.json

The single canonical fixture both implementations must satisfy.

## Location

`scripts/analysis/reconciliation_contract.json`

## Schema

```jsonc
{
  "notes": string,            // human note documenting the canonical-name mapping
  "cases": [
    {
      "name":   string,        // unique case id
      "sum":    number,        // sibling/entry sum
      "total":  number | null, // NF/document total; null = missing
      "status": "within" | "over" | "under" | "unknown"
    }
  ]
}
```

## Canonical cases (required minimum — FR-002)

| name                         | sum      | total    | status   |
|------------------------------|----------|----------|----------|
| exact_match                  | 100.0    | 100.0    | within   |
| abs_band_inclusive           | 100.05   | 100.0    | within   |
| abs_only_small_total         | 0.54     | 0.50     | within   |
| abs_only_small_total_under   | 0.46     | 0.50     | within   |
| rel_band_inside              | 10400.0  | 10000.0  | within   |
| rel_band_exact_excluded      | 10500.0  | 10000.0  | over     |
| clear_over                   | 200.0    | 100.0    | over     |
| clear_under                  | 50.0     | 100.0    | under    |
| null_total                   | 100.0    | null     | unknown  |
| zero_total                   | 100.0    | 0.0      | unknown  |
| negative_total               | 100.0    | -5.0     | unknown  |

Rationale per case is documented in `research.md` §R4. `rel_band_inside` (diff 400, rel 0.04,
above the abs band but inside the rel band) + `rel_band_exact_excluded` (diff 500, rel exactly
0.05) together lock the abs-inclusive (`<=`) / rel-strict (`<`) asymmetry — a unilateral flip
of either operator changes one of these two. `abs_only_small_total` / `abs_only_small_total_under`
(total 0.50, diff 0.04 — rel 8% **excludes** it, so only the abs band can keep it `within`) lock
the abs band itself: for typical totals the rel band already swallows a 0.05 diff, so without a
small-total case lowering/deleting the abs tolerance would pass undetected (the actual blocking
finding on PR #61). They cover both the over (`sum>total`) and under (`sum<total`) directions.

## Consumer contracts

### Python — `scripts/tests/test_reconciliation_contract.py`

For each case: `nf_groups.reconcile_group(sum, total)` mapped through
`{"reconciled":"within","over_claim":"over","under_claim":"under",None:"unknown"}`
MUST equal `case["status"]`.

### TypeScript — `src/lib/documents.test.mjs`

For each case: `documentStatus(sum, total ?? null)` MUST equal `case["status"]`
(canonical names already match the TS vocabulary).

## Drift guarantee (FR-006)

Changing `AMOUNT_ABS_TOL`/`AMOUNT_REL_TOL` or the `<=`/`<` operators in `nf_groups.py`, or
`ABS_TOL`/`REL_TOL` or the comparisons in `documents.ts`, without an equal change to the
other file AND the fixture, flips at least one case and fails that side's test.
