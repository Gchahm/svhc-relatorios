# Feature Specification: Trim feature-054 correction integration tests

**Feature Branch**: `060-trim-correction-integration-tests`
**Created**: 2026-06-14
**Status**: Draft
**Input**: GitHub issue #100 — "TEST-005: Trim feature-054 correction integration tests (~50% CI e2e cut, no coverage loss)"

## Overview

The feature-054 data-correction integration suite
(`scripts/integration_tests/test_corrections_d1.py`, merged in #99) roughly **tripled** the CI
`e2e` job: its heavy step ("Python integration tests (real D1 writebacks)") jumped from ~7 min to
22+ min, pushing total CI from ~10 min to 22+ min. The file is the entire delta — it adds 7 tests,
each driving the **unstubbed** apply→analyze pipeline where every D1 read/write is a separate
`wrangler d1 execute` subprocess (~1–2 s of startup each).

This feature trims the file's cost ~50% **without reducing real-pipeline coverage**. The granular
logic is already covered by the fast, mocked unit suite (`scripts/tests/test_corrections.py`); the
integration layer only needs to prove the real wiring at smoke depth (the documented e2e
philosophy: "one happy path + the auth gate per surface"). All changes are confined to the one test
file.

## Why the cut is safe (cost model, measured)

The expensive unit is a **full propagation** = `apply_extractions` + `run_analysis`, each a fan-out
of `wrangler d1 execute` subprocesses. Per-test `restore()` adds a cleanup `execute_sql` + a full
re-seed upsert. Across the suite:

| | per-test `restore()` | `apply_extractions` | `run_analysis` |
|---|---|---|---|
| **Before (7 tests)** | 7 | 16 | 9 |
| **After (4 tests)** | 0 | 8 | 4 |

Four of the seven tests (`test_apply_pass_records_and_changes`, `test_undo_restores_and_records`,
`test_second_undo_rejected`, `test_record_survives_cache_wipe`) all repeat the **same arrange** —
stage 800 → correct to 250 → applied — then each re-does a full stage+apply just to assert one more
thing. They are merged into a single lifecycle test that performs one stage + one apply + one undo
while preserving every assertion.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - CI maintainer: faster e2e job (Priority: P1)

As a CI maintainer, I want the correction integration suite to run in roughly half the wall-clock
time so the `e2e` job returns to its prior ~7-min duration and total CI returns to ~10 min, without
losing confidence that the real apply→analyze→correct wiring works.

**Why this priority**: The 22+ min CI step is the direct cost this issue exists to remove; it is the
primary user-facing value.

**Independent Test**: Run `pnpm test:py:integration` and confirm `TestCorrectionsD1` reports exactly
4 tests run, all passing.

**Acceptance Scenarios**:

1. **Given** the trimmed file, **When** `pnpm test:py:integration` runs, **Then** exactly 4 test
   methods in `TestCorrectionsD1` execute and all pass.
2. **Given** the CI `e2e` job, **When** it runs the integration step, **Then** the step's body cost
   is roughly halved versus the 7-test version (8 `apply_extractions` + 4 `run_analysis` + 0
   per-test `restore()` vs 16 + 9 + 7).

---

### User Story 2 - Maintainer: no coverage loss (Priority: P1)

As a maintainer, I want every real-pipeline code path the 7-test version exercised to remain
exercised after the trim — the applied/verify-after-pass lifecycle (record + list + cache-wipe
durability + undo + second-undo rejection), the rollback path, the no-op path, and the
unverifiable/fail-closed path.

**Why this priority**: The trim is only acceptable if it loses no real-pipeline coverage; this is the
explicit non-goal guard in the issue.

**Independent Test**: Inspect the trimmed file: the lifecycle test asserts all merged assertions, and
the three distinct-path tests are retained unchanged.

**Acceptance Scenarios**:

1. **Given** the trimmed file, **When** the single lifecycle test runs, **Then** it asserts:
   applied result, data change (extracted amount 250), finding cleared, the full audit-row fields
   (`from_value`/`to_value`/`evidence`/`agent`/`page_label`/`target_finding_key`/`period`/`created_at`),
   cache-wipe durability (SC-004), undo restores the value (800) and the original finding reappears
   with `reverted`/`reverted_by`/`reverted_at` set (SC-003), and a second undo of the now-reverted
   batch returns `rejected` (FR-008).
2. **Given** the trimmed file, **When** it runs, **Then** `test_apply_fail_rolls_back_byte_for_byte`
   (rollback / SC-002), `test_no_op_writes_no_row`, and `test_unverifiable_writes_no_row` are
   retained unchanged, each exercising a distinct code path.

---

### User Story 3 - Maintainer: clean shared-process baseline (Priority: P2)

As a maintainer, I want the integration suite (which runs all modules in ONE process against a
shared Miniflare D1) to leave a clean synthetic baseline for later modules, even though per-test
`restore()` is removed.

**Why this priority**: Correctness of the shared-process baseline must survive removing the per-test
re-seed; if it didn't, later integration modules could see dirty state.

**Independent Test**: Run the full `pnpm test:py:integration` suite (all modules) and confirm later
modules still pass.

**Acceptance Scenarios**:

1. **Given** the trimmed file, **When** `setUp` runs, **Then** it does **not** call `h.restore()`;
   each test re-establishes E3 via `_stage_and_propagate` and cleans its own `data_corrections`
   rows.
2. **Given** the trimmed file, **When** `tearDownClass` runs, **Then** it still calls `h.restore()`
   and drops the suite's `data_corrections` rows.

---

### Edge Cases

- What happens when a prior test left `data_corrections` rows for E3? `setUp` deletes this
  attachment's rows before each test, so each test starts from a clean correction slate.
- What happens to later integration modules sharing the process? `tearDownClass` restores the
  synthetic baseline and drops the suite's correction rows, so they see a clean seed.
- What happens if alerts accumulated across tests? They cannot — `run_analysis` rewrites the
  `2099-01` alerts via an atomic DELETE+INSERT per `reference_period` (feature 024).

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: `test_corrections_d1.py` MUST contain exactly **4** test methods:
  `test_applied_lifecycle_record_list_durability_undo`, `test_apply_fail_rolls_back_byte_for_byte`,
  `test_no_op_writes_no_row`, `test_unverifiable_writes_no_row`.
- **FR-002**: `setUp` MUST NOT call `h.restore()`; it MUST keep the rest of its body (resolve E3
  attachment/entry/period, make a temp cache dir, delete this attachment's `data_corrections` rows).
- **FR-003**: `tearDownClass` MUST still call `h.restore()` and drop the suite's `data_corrections`
  rows (unchanged).
- **FR-004**: The new lifecycle test MUST preserve all assertions from the four deleted tests in one
  pipeline pass (one stage + one apply + one undo), per US2 acceptance 1.
- **FR-005**: The retained tests `test_apply_fail_rolls_back_byte_for_byte`,
  `test_no_op_writes_no_row`, `test_unverifiable_writes_no_row` MUST be unchanged.
- **FR-006**: `import shutil` MUST be present at module top level (the cache-wipe assertion uses it);
  no unused imports may be introduced, and the now-redundant inline `import shutil` in the deleted
  durability test must not survive.
- **FR-007**: The module docstring MUST be updated if its US1/US2/US3 bullet list no longer matches
  the test layout.
- **FR-008**: No change to any non-test file — specifically not `scripts/analysis/corrections.py`,
  the harness `scripts/integration_tests/_harness.py`, the unit suite, or any app/schema/migration
  file.

### Key Entities *(include if feature involves data)*

- **`TestCorrectionsD1`**: the test class in `scripts/integration_tests/test_corrections_d1.py` —
  the only artifact this feature edits.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: `pnpm test:py:integration` passes locally with `TestCorrectionsD1` reporting 4 tests
  run, 0 failures, 0 errors.
- **SC-002**: The integration-test-body cost (subprocess fan-out) is reduced ~50%: 8
  `apply_extractions` + 4 `run_analysis` + 0 per-test `restore()` (down from 16 + 9 + 7).
- **SC-003**: The four real-pipeline code paths previously covered (applied-lifecycle, rollback,
  no-op, unverifiable) all remain covered.
- **SC-004**: The CI `e2e` job is green and its integration step returns to roughly its pre-#99
  duration.

## Assumptions

- The issue body's measured local result (`Ran 4 tests in 466.346s ... OK`) is authoritative for the
  expected shape of the change; the exact code blocks in the issue are adopted verbatim where given.
- E3 is a singleton synthetic attachment (no shared-NF sibling), so `_affected_scope` = `[E3]` and
  every detection / verify-after is E3-scoped — removing the per-test global re-seed is safe because
  no test asserts on global/E4/alert state and `run_analysis` rewrites the `2099-01` alerts
  atomically (feature 024), never accumulating across tests.
- `data_corrections` is outside the harness's synthetic analysis-owned reset set, so each test (and
  `tearDownClass`) must delete its own correction rows explicitly — unchanged behavior.

## Non-goals

- Do NOT reduce coverage of the rollback / no-op / unverifiable paths.
- Do NOT stub the real pipeline — this layer exists to exercise the unstubbed
  `apply_extractions` + `run_analysis` wiring.
- No D1 schema/migration change, no app-code change, no harness change.
