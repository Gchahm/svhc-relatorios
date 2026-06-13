# Feature Specification: Python coverage measurement + analysis-core unit tests

**Feature Branch**: `044-python-coverage-tests`
**Created**: 2026-06-12
**Status**: Draft
**Input**: User description: "full Python coverage measurement + unit tests for analysis core (mismatches, checks, nf_groups, attachments, verdicts)"
**Issue**: TEST-002 (#69), depends on TEST-001 CI (#68, merged)

## User Scenarios & Testing *(mandatory)*

### User Story 1 - The alert-generating analysis core is covered by tests (Priority: P1)

A maintainer changes `mismatches.py`, a `checks/*` module, `nf_groups.py`, `attachments.py`
roll-up, or `verdicts.py` — the modules that produce the alerts users act on and the
loop-termination signals — and the existing stdlib `unittest` suite catches a regression
before it ships, without any wrangler/D1/network/playwright dependency.

**Why this priority**: These modules generate the user-facing findings (over-claims, mismatch
alerts, vendor-concentration warnings) and decide when the self-improving loop stops. A silent
regression here corrupts the product's core output. They are also currently the largest untested
surface.

**Independent Test**: Run `pnpm test:py` (stdlib `unittest`) on a checkout with new tests; the new
test files exercise each module's pure logic against in-memory fixtures and pass with zero external
processes.

**Acceptance Scenarios**:

1. **Given** a persisted `attachment_analyses` set with mixed match flags + a page-error, **When**
   `detect_attachment_mismatches` runs, **Then** it yields exactly one mismatch per failing
   field per attachment, a page-error short-circuits that attachment's field checks, and each
   mismatch carries the correct ledger/extracted values.
2. **Given** a shared-NF group's sibling sum and an NF total, **When** `reconcile_group` /
   `within_tolerance` run across the boundary cases, **Then** the reconciled / over_claim /
   under_claim / None classification matches the documented tolerance (≤R$0.05 abs OR <5% rel).
3. **Given** per-page extraction records bundling invoice + boleto + payment-proof pages, **When**
   `build_attachment_analysis` rolls them up, **Then** the amount precedence, issuer selection,
   date selection, and amount/vendor/date match flags follow the documented heterogeneity rules,
   and a sibling fan-out reuses the representative's extraction.
4. **Given** a verdicts file with verdicts across iterations, **When** `loop_state` recomputes,
   **Then** the open set, findings, data-quality items, `affected_attachment_ids`, and the
   `terminate` signal (converged / no-progress / max-iterations) are deterministic and match the
   documented rules.

---

### User Story 2 - Coverage is measured and ratcheted in CI (Priority: P2)

A maintainer (or CI) runs a coverage command that measures the analysis/scraper pure surface,
prints a report, and fails if coverage drops below a recorded baseline — so the gap that hid these
untested modules can never silently reopen.

**Why this priority**: Without measurement, coverage erosion is invisible (the issue's core
complaint). The ratchet turns the one-time test investment into a durable floor. It depends on the
tests (US1) existing to have a meaningful baseline, hence P2.

**Independent Test**: Run the coverage command locally; confirm it reports a percentage for the
in-scope modules and exits non-zero when the percentage is below the configured floor (verified by
temporarily lowering coverage or raising the floor).

**Acceptance Scenarios**:

1. **Given** the test suite, **When** the coverage command runs, **Then** it produces a coverage
   report scoped to `scripts/analysis/` + `scripts/scraper/` (excluding the playwright/wrangler
   orchestration modules) and prints the total percentage.
2. **Given** a configured baseline floor, **When** total coverage is below it, **Then** the command
   exits non-zero (CI fails); when at/above it, the command exits zero.

---

### User Story 3 - Coverage runs in the TEST-001 CI pipeline (Priority: P3)

Every PR runs the Python coverage gate as a visible CI step, alongside the existing lint / format /
test / typecheck steps.

**Why this priority**: Wiring into CI makes the ratchet enforce on every PR rather than relying on
local discipline. It is last because the gate is useful locally even before it is wired (and the CI
edit may require a manual push due to the missing `workflow` OAuth scope — see Assumptions).

**Independent Test**: Inspect `.github/workflows/ci.yml`; a Python-coverage step invokes the
coverage command, and a dry CI run (or manual trigger) shows the step executing.

**Acceptance Scenarios**:

1. **Given** the CI workflow, **When** a PR is opened, **Then** a Python coverage step runs the
   coverage command and the job fails if coverage drops below the baseline.

---

### Edge Cases

- A module mixing pure logic with D1 calls: tested only through its pure seams (return-SQL builders,
  provider injection in `build_attachment_analysis`, in-memory `PeriodData`/`RefIndex` fixtures) — no
  test ever invokes wrangler/D1/network/playwright.
- The coverage tool is not a project dependency: it must be obtainable without adding it to
  `scripts/pyproject.toml` (run-scoped, e.g. `uv run --with coverage`).
- A test importing a `checks` module must not transitively import playwright (the `checks` tree is
  stdlib + `common` only; verified).
- Baseline floor is set slightly below the measured baseline (a small margin) so trivial
  non-functional refactors don't trip it, while a real coverage drop does.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The repo MUST provide a command that measures statement coverage of the in-scope
  Python modules and prints a report, obtainable without adding a coverage tool to the project's
  declared dependencies.
- **FR-002**: Coverage scope MUST include `scripts/analysis/` and `scripts/scraper/`, EXCLUDING the
  modules that require playwright/wrangler/network to execute: `scripts/scraper/extractors/`,
  `scripts/scraper/browser.py`, `scripts/scraper/runner.py`, `scripts/scraper/config.py`,
  both `__main__.py`, and the test files themselves. `scripts/common/d1.py` is out of the measured
  scope (its execution paths shell out to wrangler — TEST-004).
- **FR-003**: The coverage command MUST fail (non-zero exit) when total coverage of the in-scope
  modules drops below a recorded baseline floor, and succeed at/above it (the ratchet).
- **FR-004**: The baseline floor and the current measured baseline percentage MUST be recorded in
  the repo (in the coverage config and/or the PR body) so the ratchet is auditable.
- **FR-005**: New unit tests MUST cover, prioritized by risk: `mismatches.py` and `checks/*` first,
  then `nf_groups.py` tolerance math, `attachments.py` roll-up (incl. fan-out + group amount-match),
  `verdicts.py`. As coverage permits within scope, `documents.py` id derivation, `extractions.py`
  plan/summary/scoping pure logic, `loader.py`/`images.py` pure helpers, `vendor_match.py`, and
  `trends.py` SHOULD also be covered.
- **FR-006**: All new tests MUST use stdlib `unittest`, pure-function style with in-memory fixtures,
  and MUST NOT add a mocking framework or any new pip dependency to the project. Where a module mixes
  pure logic with D1 calls, tests go through the existing seams (return-SQL builders, provider
  injection) — they MUST NOT invoke wrangler/D1/network/playwright.
- **FR-007**: New tests MUST be discoverable by the existing runner (`pnpm test:py` →
  `unittest discover -s tests -t .` from `scripts/`), keeping the existing convention, and MUST pass.
- **FR-008**: The coverage gate MUST be wired into the TEST-001 CI workflow as a visible step.
- **FR-009**: The plain `pnpm test:py` runner MUST keep working unchanged (coverage is additive — a
  separate command/script), so a contributor without the coverage tool can still run the suite.

### Key Entities *(include if feature involves data)*

- **Coverage config**: the configuration that defines the measured scope (include/omit), the
  baseline floor, and the report format. Lives in the repo (e.g. a `.coveragerc` / config section).
- **Coverage command**: the additive npm script (e.g. `test:py:cov`) that runs the suite under the
  coverage tool and applies the ratchet.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: The prioritized modules (`mismatches.py`, `checks/advanced.py`,
  `checks/attachments.py`, `nf_groups.py`, `attachments.py`, `verdicts.py`) each reach at least 80%
  statement coverage, measured by the new command.
- **SC-002**: Total in-scope coverage is measured and recorded as a baseline; the gate fails when a
  change drops total coverage below the recorded floor (demonstrated locally).
- **SC-003**: The full Python suite (`pnpm test:py`) passes with the new tests added, using only the
  stdlib and zero new project dependencies; no test spawns wrangler/D1/network/playwright.
- **SC-004**: The coverage step is present and runs in the CI workflow.

## Assumptions

- **Coverage tool**: `coverage.py` is the de-facto standard and the only practical option (stdlib
  has no coverage measurement). To honor the repo's no-new-deps stance it is run **run-scoped** via
  `uv run --with coverage …`, so it is NOT added to `scripts/pyproject.toml`. Confirmed available in
  the sandbox (`coverage 7.14.1`).
- **Scope exclusions**: `runner.py`, `browser.py`, `config.py`, `extractors/`, both `__main__.py`,
  and `common/d1.py` are excluded from the coverage scope because exercising them needs a live
  portal / wrangler — out of scope per the issue (deferred to TEST-004).
- **Baseline floor**: set a few points below the measured baseline (a small safety margin) to
  tolerate trivial refactors while still catching real regressions. The exact measured baseline %
  is recorded in the PR body after the suite is written.
- **Per-module 80% target (SC-001)** applies to the prioritized modules; the global floor (FR-003)
  is the enforced gate.
- **CI push caveat**: wiring the gate into `.github/workflows/ci.yml` requires the `workflow` OAuth
  scope, which the working token lacks. If `git push` is rejected for that reason, the CI edit is
  committed on the feature branch and a manual push is requested (the test + coverage-config changes
  are independent and land regardless). The tests themselves can land without the CI edit (per the
  issue: "the tests themselves can land independently").
- **No schema/data**: this feature reads no D1/R2, writes nothing, and changes no schema/migration.
