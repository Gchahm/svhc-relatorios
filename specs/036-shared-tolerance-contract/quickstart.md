# Quickstart: Shared reconciliation tolerance/status contract

## Run the contract tests

From the repo root:

```bash
# Both suites (one command — the new `test` script):
pnpm test

# Or individually:
node --test "src/**/*.test.mjs"                          # TypeScript contract test
python -m unittest discover -s scripts/tests -t scripts  # full Python suite (incl. contract)
```

Both must report all-pass against current code.

## Prove the drift guard works (manual)

```bash
# 1. Break the Python side only:
sed -i 's/AMOUNT_ABS_TOL = 0.05/AMOUNT_ABS_TOL = 0.50/' scripts/analysis/nf_groups.py
python -m unittest scripts.tests.test_reconciliation_contract   # FAILS
git checkout scripts/analysis/nf_groups.py

# 2. Break the TS side only:
sed -i 's/const ABS_TOL = 0.05/const ABS_TOL = 0.50/' src/lib/documents.ts
node --test "src/**/*.test.mjs"                                 # FAILS
git checkout src/lib/documents.ts
```

## Files

- `scripts/analysis/reconciliation_contract.json` — canonical fixture (single source of truth).
- `scripts/tests/test_reconciliation_contract.py` — Python contract test.
- `src/lib/documents.test.mjs` — TypeScript contract test (Node built-in runner).
- `scripts/analysis/nf_groups.py`, `src/lib/documents.ts` — cross-reference comments added.
- `package.json` — `test` script runs both suites.

## Notes

- The TS test imports the **real** `documentStatus` from `documents.ts`; Node 22.18+ strips
  TS types natively, so no build/bundler/dependency is needed. A benign
  `MODULE_TYPELESS_PACKAGE_JSON` warning may print — it does not affect the result.
- No production behavior, schema, or dependency changed.
