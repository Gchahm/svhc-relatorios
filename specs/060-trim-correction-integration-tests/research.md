# Research: Trim feature-054 correction integration tests

No NEEDS CLARIFICATION markers remained from the spec; the issue body resolved every decision with
verbatim code and a measured cost model. This document records the load-bearing decisions.

## Decision 1 — Remove per-test `restore()`, keep it in `tearDownClass`

- **Decision**: Drop `h.restore()` from `setUp`; retain it (plus the suite's `data_corrections`
  cleanup) in `tearDownClass`.
- **Rationale**: Each test already fully re-establishes E3 via `_stage_and_propagate`
  (`mark_pending` invalidates staging → `record_classification` → `apply_extractions` rolls up), so
  the per-test global re-seed is redundant. It is safe to remove because: E3 is a singleton (no
  shared-NF sibling), so `_affected_scope` = `[E3]` and every detection
  (`summarize_mismatches(attachment_ids=[E3])`, `apply_correction`'s verify-after) is E3-scoped; no
  test asserts on global/E4/alert state; `run_analysis` rewrites the `2099-01` alerts via an atomic
  DELETE+INSERT per `reference_period` (feature 024), so alerts are rewritten, never accumulated
  across tests. `tearDownClass` still resets the baseline for later modules in the shared process.
- **Alternatives considered**: Keep `restore()` but make it cheaper — rejected; it is not the
  granular per-test correctness lever, just a redundant re-seed, and removing it is the bulk of the
  measured CI saving (7 fewer cleanup+upsert pairs).

## Decision 2 — Collapse the four `applied`-path tests into one lifecycle test

- **Decision**: Delete `test_apply_pass_records_and_changes`, `test_undo_restores_and_records`,
  `test_second_undo_rejected`, `test_record_survives_cache_wipe`; replace with one
  `test_applied_lifecycle_record_list_durability_undo` (one stage + one apply + one undo) that
  preserves every assertion.
- **Rationale**: All four repeat the identical arrange (stage 800 → correct to 250 → applied) and
  then each re-runs a full stage+apply solely to assert one additional fact. A single pipeline pass
  can chain record → list/audit → cache-wipe durability → undo → second-undo rejection, halving the
  expensive `apply_extractions`/`run_analysis`/`undo` subprocess fan-out while losing no assertion.
  The granular logic is independently covered by the fast mocked unit suite
  (`scripts/tests/test_corrections.py`).
- **Alternatives considered**: Mark the redundant tests `@skip` — rejected; leaves dead code and
  still confuses the coverage picture. Stub the pipeline — rejected; the explicit non-goal is to
  keep this layer exercising the **unstubbed** wiring.

## Decision 3 — Retain rollback / no-op / unverifiable tests unchanged

- **Decision**: Leave `test_apply_fail_rolls_back_byte_for_byte` (SC-002),
  `test_no_op_writes_no_row`, and `test_unverifiable_writes_no_row` exactly as-is.
- **Rationale**: Each exercises a distinct real-pipeline code path not reachable from the applied
  lifecycle; collapsing them would lose coverage, which the issue forbids.

## Decision 4 — `import shutil` at module top

- **Decision**: Add `import shutil` to the module-level import block; remove the inline
  `import shutil` that lived inside the deleted durability test.
- **Rationale**: The lifecycle test's cache-wipe step uses `shutil.rmtree`; a module-level import is
  the clean form and avoids an unused-import lint hit once the inline one is gone.
