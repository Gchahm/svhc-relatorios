# Feature Specification: TypeScript component/unit test harness for the dashboard

**Feature Branch**: `045-ts-test-harness`
**Created**: 2026-06-13
**Status**: Draft
**Input**: User description: "Add a TypeScript component/unit test harness covering the dashboard client components and API route logic for the SVHC fiscal-auditing dashboard"

## Overview

The fiscal-auditing dashboard's TypeScript side has only three pure-logic test files
(`src/lib/alerts.test.mjs`, `src/lib/documents.test.mjs`,
`src/app/dashboard/entries/deepLink.test.mjs`), all run via Node's built-in `node:test`
with native TypeScript type-stripping. Everything React renders is untested, and the API
route handlers (auth-gating, response shape) are untested. A reviewer or maintainer changing
any of these surfaces has no automated regression signal — and the surfaces in question are the
ones that decide what evidence a fiscal auditor sees (deep-link resolution, alert metadata →
affected-entry links, document over/within/under status badge, the not-found notice).

This feature adds a maintainable TypeScript test harness that closes those gaps, runs under one
command wired into CI, and reports coverage for `src/` with a recorded baseline and a ratchet —
mirroring the Python coverage policy already in place (TEST-002 / #69).

## Clarifications

### Session 2026-06-13

Running unattended, the worker resolved the spec's decision points with informed defaults
(recorded here and in Assumptions) rather than pausing for interactive answers:

- Q: Harness — minimal stdlib (`node:test`) vs. component-test deps (`vitest`+RTL+DOM)? → A:
  Minimal stdlib by default; extract client logic into pure modules and pin them. Adopt a DOM
  harness only if a flow cannot be verified by pure extraction. The entries deep-link view-state
  is verifiable by extracting a pure decision module, so **no new dependency is added**.
- Q: How is `src/` coverage measured without a new dependency? → A: Node's built-in
  `node --test --experimental-test-coverage` (the runner is already `node --test`); a small repo
  script parses its summary and enforces a recorded baseline + ratchet, mirroring `test:py:cov`.
- Q: Pin a specific auth status code (401 vs 403)? → A: No — pin the allow/deny **decision** and
  the unauthorized **status constant read from the handler code**, so the test follows the code
  (the routes currently return 403) rather than independently hardcoding a number.
- Q: Single command name — `test:ts` or new `test:unit`? → A: Extend the existing `test:ts`
  (already wired into `pnpm test` and the CI TypeScript-tests step); add `test:ts:cov` for the
  coverage+ratchet gate, mirroring `test:py` / `test:py:cov`.
- Q: Scope of API-handler extraction — all routes or the three named? → A: The three named
  surfaces (`/api/alerts`, `/api/documents`, `/api/attachment-analyses/...`) plus the shared auth
  decision they all use; other routes are out of scope for this issue.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - A maintainer runs the whole TS test suite with one command (Priority: P1)

A developer (or CI) runs a single command and sees every TypeScript test — the existing
pure-logic tests plus the new client-logic and API-handler tests — execute and report pass/fail
plus a coverage summary for `src/`.

**Why this priority**: Without a single entry point wired into CI, the tests are invisible and
rot. This is the foundation every other story builds on, and it is the gate the issue requires.

**Independent Test**: Run the wired command (`pnpm test:ts`) on a clean checkout; observe all
TS tests run, a coverage summary printed for `src/`, and a nonzero exit on any failure. The CI
workflow's TypeScript-tests step invokes this same command and fails the run on a regression.

**Acceptance Scenarios**:

1. **Given** a clean checkout, **When** the maintainer runs the single wired command, **Then**
   all existing and new TypeScript tests execute and the command exits zero only if all pass.
2. **Given** a pull request that breaks a covered behavior, **When** CI runs, **Then** the
   TypeScript-tests step fails and the PR is blocked.
3. **Given** the suite runs, **When** it finishes, **Then** a coverage summary for `src/` is
   produced and compared against a recorded baseline; coverage dropping below the baseline fails.

---

### User Story 2 - Alerts metadata → affected-entry links and type labels are pinned (Priority: P1)

The alerts surface turns an alert's stored `metadata` JSON into a list of affected ledger
entries (single `entry_id` vs. an `entry_ids[]` array), builds a deep-link URL per entry, and
renders a human-readable type label (never raw `snake_case` — feature 038 / IMP-010). These are
the exact behaviors an auditor relies on to jump from an alert to the offending entries.

**Why this priority**: This is core auditing-evidence routing; a silent regression here
mis-routes or hides findings. The logic is pure and already partly extracted (`src/lib/alerts.ts`),
so it is high-value and low-cost to pin.

**Independent Test**: Feed representative `metadata` JSON (single id, multi-id array, malformed,
null) to the parsing function and assert the affected-entry list; assert the deep-link URL shape;
assert every alert type renders a localized label with no underscores.

**Acceptance Scenarios**:

1. **Given** metadata `{"entry_id":"<uuid>"}`, **When** affected entries are derived, **Then**
   the result is exactly `["<uuid>"]`.
2. **Given** metadata `{"entry_ids":["a","b"]}`, **When** affected entries are derived, **Then**
   the result is `["a","b"]` (array form is honored).
3. **Given** malformed or null metadata, **When** affected entries are derived, **Then** the
   result is `[]` and nothing throws.
4. **Given** any alert type the pipeline emits, **When** its label is rendered, **Then** the
   label is the localized (pt-BR catalog) value and contains no `snake_case` underscores.
5. **Given** a period and an entry id, **When** a deep link is built, **Then** the URL is the
   `/dashboard/entries?period=…&entry=…` shape the entries surface consumes.

---

### User Story 3 - Document status badge math matches the shared tolerance contract (Priority: P2)

The documents surface shows an over / within / under / unknown status badge derived from the
sum of linked entries vs. the document total, using the tolerance contract that mirrors the
Python reconciliation (feature 036). The badge label is the localized catalog string.

**Why this priority**: A wrong badge misleads an auditor about whether an invoice is over-claimed.
The math already has a cross-language contract test (`documents.test.mjs`); this story extends
coverage to the badge-label mapping (status → localized label) that the contract test does not
touch.

**Independent Test**: For each status value, assert the badge maps to the correct localized
catalog label; reuse the shared reconciliation fixture for the math itself.

**Acceptance Scenarios**:

1. **Given** each `DocumentStatus` value, **When** the badge label is resolved, **Then** it equals
   the corresponding pt-BR catalog label (`status.over/within/under/unknown`).
2. **Given** the shared reconciliation fixture, **When** `documentStatus` is evaluated, **Then**
   every case matches the contract (already pinned; retained, not duplicated).

---

### User Story 4 - Entries deep-link end-to-end client behavior is verified (Priority: P2)

The entries surface reads `?period=` and `?entry=` params, selects the period, scrolls to and
highlights the row, auto-opens the analysis dialog when an analysis exists, and shows the
feature-037 not-found notice when the entry cannot be resolved. The pure decision core
(`resolveDeepLink`) is already tested; this story verifies the surrounding view-state behavior the
decision drives, for the highest-risk interactive flow.

**Why this priority**: The deep-link flow is the single most stateful interactive path and the
one most likely to silently break. It is the one flow that justifies rendering-level testing
(see Assumptions on the harness exception).

**Independent Test**: Drive the deep-link-driven view-state logic with deep-link params for a
present entry, an absent entry, and an invalid id; assert it selects the right period, surfaces
the right row/dialog/highlight state, and resolves the localized not-found / invalid notice text
in the not-found and invalid cases.

**Acceptance Scenarios**:

1. **Given** params pointing at a present entry with an analysis, **When** the surface resolves
   the link, **Then** the matching row is highlighted and its analysis dialog auto-opens.
2. **Given** params pointing at an absent entry, **When** the surface resolves the link, **Then**
   the localized feature-037 not-found notice is selected and no dialog opens.
3. **Given** an invalid (non-UUID) entry id, **When** the surface resolves the link, **Then** the
   localized invalid notice is selected and no lookup is attempted.

---

### User Story 5 - API route handler shape + auth-gating is pinned without Cloudflare plumbing (Priority: P2)

The list/detail API routes (`/api/alerts`, `/api/documents`, `/api/attachment-analyses/...`)
gate on an authenticated session with an allowed role (returning an unauthorized status
otherwise) and shape DB rows into a stable response JSON. The pure pieces — the auth decision and
the row-to-response shaping — are pinned without standing up the Cloudflare runtime.

**Why this priority**: A regression in the auth decision is a security issue; a regression in the
response shape silently breaks every consuming surface. Extracting the pure logic from the
context plumbing is the issue's stated approach and keeps the tests stdlib-friendly.

**Independent Test**: Call the extracted auth-decision function with sessions of each role
(none, disallowed, allowed) and assert allow/deny; call the extracted shaping function with
representative DB rows and assert the response JSON shape (including the documents `status` field
computed via the shared tolerance contract).

**Acceptance Scenarios**:

1. **Given** no session, **When** the auth decision runs, **Then** it denies (unauthorized).
2. **Given** a session whose role is not allowed, **When** the auth decision runs, **Then** it
   denies.
3. **Given** a session whose role is allowed, **When** the auth decision runs, **Then** it allows.
4. **Given** representative DB rows for a route, **When** the shaping function runs, **Then** the
   response JSON has the documented fields and types (and, for documents, the correct `status`).

---

### Edge Cases

- Malformed / null / non-object `metadata` JSON → affected-entry list is empty, never throws.
- An `entry_ids` array containing non-string or empty values → only valid ids are surfaced.
- A document with a null or non-positive total → status is `unknown`.
- A deep link whose entry exists but is filtered out vs. one that does not exist at all → the
  recovery-vs-not-found distinction is preserved (already pinned by `deepLink.test.mjs`; the
  client story asserts the user-visible consequence).
- An alert type absent from the curated label map → a humanized (no-underscore) fallback label,
  never raw `snake_case`.
- The coverage ratchet: a PR that raises coverage does not fail; a PR that drops it below the
  recorded baseline does.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The repository MUST provide a single command that runs every TypeScript test
  (existing pure-logic tests plus the new client-logic and API-handler tests) and exits nonzero
  on any failure.
- **FR-002**: That single command MUST be invoked by the existing CI workflow's TypeScript-tests
  step, so a covered-behavior regression blocks a pull request.
- **FR-003**: The harness MUST cover the alerts metadata → affected-entry derivation for the
  single-`entry_id`, `entry_ids[]`, malformed, and null cases, and the deep-link URL shape.
- **FR-004**: The harness MUST assert that every alert type renders a localized label with no
  `snake_case` underscores, asserting against the I18N-001 catalog labels (pt-BR), not hardcoded
  English literals.
- **FR-005**: The harness MUST cover the documents status badge mapping (each `DocumentStatus`
  value → its localized catalog label) and MUST retain the existing shared reconciliation-contract
  coverage of the status math.
- **FR-006**: The harness MUST verify the entries deep-link client behavior end-to-end for the
  present-entry, absent-entry, and invalid-id cases, including that the localized feature-037
  not-found / invalid notice text is selected in the not-found and invalid cases.
- **FR-007**: The harness MUST pin the API route auth decision (deny for no session / disallowed
  role, allow for allowed role) and the row-to-response shaping for the alerts, documents, and
  attachment-analyses routes, testing the pure logic without standing up the Cloudflare runtime.
- **FR-008**: The harness MUST produce a coverage report for `src/` and compare it against a
  recorded baseline, failing when coverage drops below the baseline (same policy as TEST-002),
  while passing when coverage is at or above the baseline.
- **FR-009**: All test text assertions on UI strings MUST reference the I18N-001 catalog
  keys/labels, never hardcoded English literals.
- **FR-010**: The harness MUST NOT add a snapshot-test or markup-dump style of assertion; tests
  assert behavior and data, not rendered-markup blobs.
- **FR-011**: Any new third-party dependency introduced MUST be explicitly justified in the spec
  and plan against the repo's no-new-deps culture; pure-logic coverage MUST use the existing
  stdlib `node:test` path by default.
- **FR-012**: The harness MUST NOT introduce end-to-end / real-browser tests (that is TEST-004).

### Key Entities *(include if feature involves data)*

- **Alert metadata**: stored JSON on an alert carrying `entry_id` or `entry_ids[]` (and other
  evidence keys) used to build affected-entry deep links and evidence fields.
- **Document status**: one of over / within / under / unknown, derived from the linked-entry sum
  vs. the document total under the shared tolerance contract; rendered as a localized badge.
- **Deep-link params**: `period` + `entry` query params the entries surface consumes to scroll,
  highlight, and auto-open the analysis dialog (or show the not-found / invalid notice).
- **Session / role**: the authenticated session and its role, the input to each route's
  allow/deny auth decision.
- **Coverage baseline**: a recorded `src/` coverage figure plus a ratchet policy, mirroring the
  Python coverage baseline.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A single documented command runs 100% of the TypeScript tests and is the command
  CI invokes; on a clean checkout it completes in well under a minute on a developer machine.
- **SC-002**: All five priority behaviors (single-command run + coverage, alerts metadata/labels,
  documents status/labels, entries deep-link client behavior, API auth + shape) have at least one
  passing test, with zero failing tests on the merged branch.
- **SC-003**: Introducing a deliberate regression in any of the five covered behaviors causes at
  least one test to fail (the suite is not vacuous).
- **SC-004**: A coverage figure for `src/` is recorded as the baseline and enforced; a change that
  lowers coverage below the baseline fails the suite, and a change that does not lower it passes.
- **SC-005**: Zero UI-string assertions use hardcoded English literals — every such assertion
  resolves its expected value from the I18N-001 catalog.
- **SC-006**: Any new dependency is justified in writing; if the minimal path is taken, the
  dependency count is unchanged.

## Assumptions

- **Harness split (informed default)**: Per the issue's pragmatic split, pure-logic coverage uses
  the existing `node:test` + native TS type-stripping path (zero new deps) by default, by
  extracting any not-yet-pure client logic into small importable modules (the established
  `deepLink.ts` pattern). Component rendering is tested **only** for the single highest-risk
  interactive flow — the entries deep-link behavior (User Story 4) — and even there the default
  approach is to extract the deep-link-driven view-state decision into a pure module and pin it,
  preferring zero new deps. A DOM-backed component-test dependency (`vitest` +
  `@testing-library/react` + a DOM) is taken **only if** that flow cannot be meaningfully verified
  by pure extraction; the plan records the decision explicitly. The bias is strongly toward the
  no-new-deps minimal path, consistent with the repo culture and the Python testing track.
- **Coverage tool**: `src/` coverage is measured with Node's built-in coverage capability
  (`node --test --experimental-test-coverage`, which is already the test runner), avoiding a new
  dependency; the baseline + ratchet is enforced by a small repo script, mirroring the Python
  `test:py:cov` approach.
- **Auth status code**: The routes currently return an unauthorized JSON response; the tests pin
  the **decision** (allow/deny) and the response **shape**, not a specific numeric status code, so
  the test stays correct whether the code is 401 or 403 — the exact code in use is asserted as a
  constant read from the handler logic, not hardcoded independently.
- **No mirror/schema/data change**: This is a test-only, presentation-and-logic-layer feature. It
  reads no new data, writes nothing, and changes no D1 schema or migration. Extraction refactors
  that move pure logic out of a client component preserve that component's existing behavior.
- **Localization baseline**: The dashboard was localized to pt-BR in #72–#75 (I18N-001..004);
  assertions reference the catalog as the source of truth for expected labels.
