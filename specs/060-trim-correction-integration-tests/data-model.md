# Data Model: Trim feature-054 correction integration tests

This feature introduces and changes **no persisted data model** — it edits one test file only. No D1
schema, no migration, no Drizzle change. The entities below are the test-fixture entities the suite
already relies on (documented for context, not modified).

## Test-fixture entities (unchanged)

- **`TestCorrectionsD1`** — the `unittest.TestCase` subclass in
  `scripts/integration_tests/test_corrections_d1.py`. After this feature it has exactly 4 test
  methods.
  - `test_applied_lifecycle_record_list_durability_undo` (new — replaces 4 tests)
  - `test_apply_fail_rolls_back_byte_for_byte` (unchanged)
  - `test_no_op_writes_no_row` (unchanged)
  - `test_unverifiable_writes_no_row` (unchanged)

- **E3** — the synthetic singleton attachment/entry pair (ledger amount 250.00, no shared-NF
  sibling) seeded by the harness on the `2099-01` period. The correction target throughout the
  suite. Scope of every detection is `[E3]`.

- **`data_corrections`** (existing D1 table, feature 054) — the audit-trail rows the suite asserts
  on via `list_corrections`. Outside the harness's synthetic analysis-owned reset set, so the suite
  deletes its own rows in `setUp` (per-attachment) and `tearDownClass` (all suite attachments).
  Read-only-asserted by this feature; not schema-changed.

## State transitions exercised (lifecycle test)

```
stage 800 (wrong extraction) ──> amount finding open
        │
   apply_correction(→250)  ──> status=applied, extracted=250, finding cleared, audit row written
        │
   cache wipe              ──> record still listable (lives in D1, not cache)  [SC-004]
        │
   undo_correction        ──> status=reverted (reverted_by/at set), extracted=800, finding reappears [SC-003]
        │
   undo_correction (2nd)  ──> result=rejected, no change  [FR-008]
```
