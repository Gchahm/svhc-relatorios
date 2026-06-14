# Quickstart: Trim feature-054 correction integration tests

## What changed

`scripts/integration_tests/test_corrections_d1.py` now has 4 test methods (down from 7), no per-test
`h.restore()`, and `import shutil` at module top. No non-test file changed.

## Verify locally

The integration suite needs `wrangler` + an applied local migration set against Miniflare D1
(`setUpClass` runs `h.seed_once()`).

```bash
# Run just this module:
pnpm test:py:integration 2>&1 | tail -40
# Expect: TestCorrectionsD1 contributes 4 tests, OK.
```

Confirm the test count and method names:

```bash
python -m unittest -v scripts.integration_tests.test_corrections_d1 2>&1 | grep -E '^test_'
# Expect exactly:
#   test_applied_lifecycle_record_list_durability_undo
#   test_apply_fail_rolls_back_byte_for_byte
#   test_no_op_writes_no_row
#   test_unverifiable_writes_no_row
```

## Acceptance recap (from the issue)

- Exactly 4 test methods, named as above.
- `setUp` no longer calls `h.restore()`; `tearDownClass` still does.
- `import shutil` present; no unused imports.
- The lifecycle test still asserts: applied result + data change + finding cleared + full audit-row
  fields + cache-wipe durability + undo restores value & finding reappears & `reverted`/
  `reverted_by`/`reverted_at` + second-undo `rejected`.
- No change to `scripts/analysis/corrections.py`, `_harness.py`, the unit suite, or any non-test
  file.
