# Feature Specification: Shared reconciliation tolerance/status contract

**Feature Branch**: `036-shared-tolerance-contract`
**Created**: 2026-06-12
**Status**: Draft
**Input**: User description: "Tie the reconciliation over/within/under tolerance logic in scripts/analysis/nf_groups.py and src/lib/documents.ts together with a shared JSON fixture and cross-language contract tests so a unilateral tolerance/status change fails CI (IMP-006, issue #43)"

## Overview

The reconciliation over/within/under decision — "does a set of sibling/linked amounts
add up to the document/NF total, within tolerance?" — exists in two independent
implementations, in two languages:

- **Python** (`scripts/analysis/nf_groups.py`): constants `AMOUNT_REL_TOL = 0.05`,
  `AMOUNT_ABS_TOL = 0.05`; `within_tolerance()` + `reconcile_group()` drive `amount_match`,
  shared-NF reconciliation, and the `document_overpayment` alert.
- **TypeScript** (`src/lib/documents.ts`): constants `REL_TOL = 0.05`, `ABS_TOL = 0.05`;
  `documentStatus()` drives the over/within/under badge on `/dashboard/documents`.

They are currently identical (same constants, same `abs-diff <= ABS || rel < REL` shape),
but nothing binds them. The first unilateral change (a rounding fix, a tolerance tweak)
makes the UI badge and the alert that created it disagree: a document can show "within"
while an unresolved `document_overpayment` alert still points at it.

This feature makes a divergence between the two implementations **fail automatically**,
so the two sides can never silently drift.

## Clarifications

### Session 2026-06-12

No critical ambiguities required interactive clarification; all decision points were
resolved with documented assumptions (see Assumptions A1–A5). Key decisions recorded:

- Q: Contract-test (Suggestion 2) vs persist-status restructure (Suggestion 3)? → A: Contract-test — cheapest correct guard; restructure is a deferred larger change (A5).
- Q: Fixture format and canonical status vocabulary? → A: JSON fixture; canonical names `within`/`over`/`under`/`unknown` (TS-flavored); Python test maps `reconcile_group` output through the equivalence (A2, Edge Cases).
- Q: TS test runner with no new dependency? → A: Node.js built-in `node --test`, importing the actual `documentStatus`, no bundler/build (A3, FR-008).

## User Scenarios & Testing *(mandatory)*

### User Story 1 - A unilateral tolerance/status change is caught before merge (Priority: P1)

A developer changes the tolerance band or the over/within/under decision on **one** side
only (e.g. bumps the Python absolute tolerance to R$0.10, or flips a boundary comparison
on the TS side). The shared contract test on the changed side fails — surfacing the drift
instead of letting the badge and the alert silently disagree in production.

**Why this priority**: This is the entire point of the issue — without it, badge↔alert
consistency relies on human memory across two files in two languages. It is the MVP.

**Independent Test**: Run the Python contract test and the TS contract test against a
shared fixture; both pass on the current (identical) code. Then locally edit one constant
on one side and re-run that side's test — it fails. Revert and both pass again.

---

### User Story 2 - The two implementations agree on every documented boundary case (Priority: P2)

The reconciliation status for the same `(sum, total)` input is the same whether it is
computed by the Python pipeline (alert generation) or the TypeScript UI (badge). A
reviewer can read one fixture file and see every boundary case (exact match, just inside
the absolute band, just inside and exactly at the relative band, just over, just under,
missing total, zero/negative total) and the single agreed status for each.

**Why this priority**: Codifies the *current* agreed behavior as the canonical contract so
the test in Story 1 has something concrete to check. Without a documented fixture the test
would just re-encode each side's logic separately and could itself drift.

**Independent Test**: Inspect the fixture file; confirm each case lists exactly one
expected status and that both language tests load that same file.

### Edge Cases

- **Exact match** (`sum == total`): status `within`.
- **Difference exactly equal to the absolute tolerance** (`|sum - total| == 0.05`): the
  `<=` absolute comparison includes it → `within`.
- **Difference just above the absolute tolerance but inside the relative band** (large
  totals, e.g. `sum=10400, total=10000`, diff `400`, rel `0.04`): `within`.
- **Difference exactly at the relative tolerance** (e.g. `sum=10500, total=10000`, diff
  `500`, rel `0.05`): the relative comparison is strict `<`, so exactly 5% is **not**
  within → `over`. The fixture pins both the just-under and the exactly-at boundary so the
  abs-inclusive / rel-strict asymmetry is locked.
- **Over** (`sum > total`, outside both bands): `over`.
- **Under** (`sum < total`, outside both bands): `under`.
- **Missing total** (`total` is null/None): `unknown`.
- **Zero or negative total** (`total <= 0`): `unknown` — cannot be reconciled.
- **Status-name mapping**: Python and TS use different names for the same four buckets
  (`reconciled`↔`within`, `over_claim`↔`over`, `under_claim`↔`under`, `None`↔`unknown`).
  The fixture uses the canonical TS-flavored names (`within`/`over`/`under`/`unknown`) as
  the single source of truth, and the Python test maps `reconcile_group`'s output through
  the documented equivalence, so the cross-language equality is explicit and tested.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The repository MUST contain a single shared fixture file enumerating
  reconciliation contract cases, each case a `(sum, total)` input and one canonical
  expected status drawn from the fixed set `within` | `over` | `under` | `unknown`.
- **FR-002**: The fixture MUST cover, at minimum: an exact match; a difference exactly at
  the absolute tolerance; a difference inside the relative band but above the absolute
  band; a difference exactly at the relative tolerance boundary (to lock the abs-inclusive
  / rel-strict asymmetry); a clear over; a clear under; a null total; and a zero/negative
  total.
- **FR-003**: A Python test MUST load the shared fixture and assert that
  `reconcile_group(sum, total)` (mapped through the documented status-name equivalence)
  equals each case's canonical expected status.
- **FR-004**: A TypeScript test MUST load the **same** shared fixture and assert that
  `documentStatus(sum, total)` equals each case's canonical expected status.
- **FR-005**: Both tests MUST currently pass against the existing implementations (the
  current behavior is the canonical contract; this feature does not change any tolerance
  value or decision boundary).
- **FR-006**: A unilateral change to either implementation's tolerance constants or
  over/within/under decision that diverges from the fixture MUST cause that side's
  contract test to fail.
- **FR-007**: The canonical-vs-mirror relationship MUST be documented in a comment on
  **both** source files (`nf_groups.py` and `documents.ts`), each pointing at the other
  and at the shared fixture, so a reader of either file knows a counterpart exists.
- **FR-008**: The TypeScript test MUST be runnable with the project's existing toolchain
  with **no new npm dependency** (the project has no test framework; use the Node.js
  built-in test runner / assertions).
- **FR-009**: The Python test MUST run under the existing stdlib `unittest` suite
  (`python -m unittest discover -s scripts/tests -t scripts`) with **no new pip
  dependency**.
- **FR-010**: The feature MUST NOT change any production behavior — no new tolerance
  values, no schema/migration change, no change to how alerts or badges are computed.

### Key Entities

- **Reconciliation contract case**: one record of `{ sum, total, status }` where `status`
  is one of `within` | `over` | `under` | `unknown`. The collection of cases is the
  canonical contract both implementations must satisfy.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: There is exactly one shared fixture file, and both the Python and the
  TypeScript contract tests read from it (verifiable by inspecting both test files'
  load path).
- **SC-002**: Running the Python suite and the TS test against current code yields 100%
  pass with zero new dependencies installed.
- **SC-003**: Changing a single tolerance constant or boundary comparison on either side
  (and not the other) makes at least one contract test fail — demonstrable by a local
  edit-and-revert.
- **SC-004**: A developer reading either `nf_groups.py` or `documents.ts` finds a comment
  naming the counterpart implementation and the shared fixture (verifiable by grep).

## Assumptions

- **A1**: The current behavior (identical 5% relative OR R$0.05 absolute band, abs
  comparison inclusive `<=`, rel comparison strict `<`) is correct and is what the
  contract should freeze. This feature is purely a drift guard, not a behavior change.
- **A2**: The fixture is authored as JSON (language-neutral, both Python `json` and
  Node.js `JSON.parse` read it natively) and stored where both test suites can reference
  it by relative path. Python tests live in `scripts/tests/`; the exact fixture location
  is chosen at plan time.
- **A3**: The TypeScript test runs via the Node.js built-in test runner (`node --test`)
  with no bundler/build step. It imports the **actual** exported `documentStatus` (or a
  byte-identical compiled form) — it never re-implements the math. The plan resolves the
  exact import mechanism (the function is pure and dependency-free, so a thin runnable
  copy or a small loader is acceptable only if it imports, not re-derives, the logic).
- **A4**: "Fail CI" is interpreted as "there exists a runnable, dependency-free test
  command that fails on drift". The repo's CI wiring is out of scope; providing the
  runnable tests and documenting the commands satisfies the intent. A dependency-free
  `test` npm script may be added.
- **A5**: We adopt the contract-test approach (issue Suggestion 2), not the persist-status
  restructure (Suggestion 3), because Suggestion 3 is a larger schema/pipeline change the
  issue itself defers (it pairs with integer-centavo amounts, IMP-001); the cross-test is
  the cheapest correct guard and is the issue's explicitly recommended option.
