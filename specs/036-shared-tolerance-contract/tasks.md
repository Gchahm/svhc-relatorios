# Tasks: Shared reconciliation tolerance/status contract

**Feature**: 036-shared-tolerance-contract
**Spec**: [spec.md](./spec.md) | **Plan**: [plan.md](./plan.md)

The contract test IS the deliverable for this feature, so test tasks are first-class (not optional).

## Phase 1: Setup

- [X] T001 Confirm Node version supports native TS type-stripping (`node --version` ≥ 22.18; container has v22.22.3) and the Python `unittest` discover command runs from repo root — no installs needed.

## Phase 2: Foundational (the shared canonical fixture — blocks both story tests)

- [X] T002 Create the canonical shared fixture `scripts/analysis/reconciliation_contract.json` with a `notes` field (documenting the canonical-name mapping) and a `cases` array covering the nine required cases from `contracts/reconciliation-contract.md` (exact_match, abs_band_inclusive, rel_band_inside, rel_band_exact_excluded, clear_over, clear_under, null_total, zero_total, negative_total).

## Phase 3: User Story 1 — Unilateral change is caught (Priority: P1) 🎯 MVP

**Goal**: A contract test on each side fails when that side's tolerance/decision diverges from the fixture.

**Independent test**: Both tests pass on current code; editing one constant on one side makes that side's test fail.

- [X] T003 [P] [US1] Add the Python contract test `scripts/tests/test_reconciliation_contract.py`: load `../analysis/reconciliation_contract.json` relative to the test file, and for each case assert `nf_groups.reconcile_group(sum, total)` mapped through `{"reconciled":"within","over_claim":"over","under_claim":"under",None:"unknown"}` equals `case["status"]`. Import `nf_groups` the same way sibling tests do.
- [X] T004 [P] [US1] Add the TypeScript contract test `src/lib/documents.test.mjs`: load the same fixture via a relative path (`../../scripts/analysis/reconciliation_contract.json`) using `node:fs`, import `documentStatus` from `./documents.ts`, and for each case assert `documentStatus(case.sum, case.total)` equals `case.status`. Use `node:test` + `node:assert/strict`.
- [X] T005 [US1] Add a dependency-free `test` script to `package.json` running both suites: `node --test "src/**/*.test.mjs" && python -m unittest discover -s scripts/tests -t scripts`.

## Phase 4: User Story 2 — Cross-language agreement + drift documentation (Priority: P2)

**Goal**: The relationship is visible from each source file, and the fixture is the single agreed source of truth.

**Independent test**: grep each source file for a comment naming the counterpart + fixture; confirm both tests read the one fixture.

- [X] T006 [P] [US2] Add a cross-reference comment to `scripts/analysis/nf_groups.py` (near `AMOUNT_REL_TOL`/`AMOUNT_ABS_TOL`) naming `src/lib/documents.ts:documentStatus` as the mirror and `scripts/analysis/reconciliation_contract.json` as the shared contract guarding them.
- [X] T007 [P] [US2] Add the symmetric cross-reference comment to `src/lib/documents.ts` (near `REL_TOL`/`ABS_TOL`) naming `scripts/analysis/nf_groups.py:reconcile_group` and the same fixture.

## Phase 5: Polish & Verification

- [X] T008 Run `pnpm test` (or both commands directly) from repo root; confirm 100% pass with zero installs.
- [X] T009 Verify the drift guard per `quickstart.md`: temporarily break each side's tolerance, confirm that side's test fails, then revert.
- [X] T010 Run `pnpm lint` and `pnpm format`; confirm the new/edited files pass and no unrelated files are reformatted.

## Dependencies

- T002 (fixture) blocks T003 and T004 (both load it).
- T003/T004 block T005 (script runs them) and T008/T009 (verification).
- T006/T007 are independent of the tests (documentation) but logically part of the same change.

## Parallel opportunities

- T003 and T004 touch different files → parallelizable after T002.
- T006 and T007 touch different files → parallelizable.

## MVP scope

User Story 1 (T001–T005) is the MVP: it delivers the failing-on-drift guard. US2 (T006–T007)
adds discoverability; Polish (T008–T010) verifies.
