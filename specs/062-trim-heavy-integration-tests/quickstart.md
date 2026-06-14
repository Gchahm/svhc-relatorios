# Quickstart: Verify the trim + wrangler-resolver change

## Run the trimmed integration suite (real Miniflare D1)

```bash
# Full suite — must exit 0; proves the trimmed modules pass AND later modules see a clean baseline.
pnpm test:py:integration

# Each trimmed module in isolation (verifies no cross-module ordering dependency):
cd scripts && SVHC_WRANGLER_PERSIST=.wrangler/state-test uv run python -m unittest -v integration_tests.test_re_derive_d1
cd scripts && SVHC_WRANGLER_PERSIST=.wrangler/state-test uv run python -m unittest -v integration_tests.test_reclassify_d1
cd scripts && SVHC_WRANGLER_PERSIST=.wrangler/state-test uv run python -m unittest -v integration_tests.test_typed_record_d1
```

## Confirm the wrangler resolver

```bash
# The local binary is resolved once at import and used directly (no npx) when present.
python -c "import sys; sys.path.insert(0,'scripts'); from common import d1; print(d1._WRANGLER)"
# -> ['/abs/path/node_modules/.bin/wrangler']  (or ['npx','wrangler'] if absent)
```

`--remote` behavior is unchanged — only the executable location differs; all flags/args are identical.

## Format gate

```bash
node_modules/.bin/prettier --check .
```

## Expected outcomes

- `pnpm test:py:integration` exits 0.
- Step wall-clock materially lower than the ~1907 s baseline.
- No assertion dropped; each module's distinct paths still covered.
- No JS/TS/schema/migration touched; only `scripts/common/d1.py` + the three test modules changed.
