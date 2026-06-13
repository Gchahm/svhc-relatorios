# Feature Specification: CI pipeline — lint, format check, both test suites, and build on every PR

**Feature Branch**: `043-ci-pipeline`  
**Created**: 2026-06-12  
**Status**: Draft  
**Input**: User description: "add a GitHub Actions CI workflow running lint, prettier check, both test suites, and the Next.js build on every PR and push to main"

> Implements GitHub issue **#68** (TEST-001).

## User Scenarios & Testing *(mandatory)*

### User Story 1 - PR author gets automatic verification (Priority: P1)

A contributor opens a pull request (or pushes to `main`). Without any manual action, an automated
pipeline runs the project's quality gates — ESLint, a read-only Prettier format check, the TypeScript
test suite, the Python test suite, and a typecheck/build — and reports a single pass/fail status on the
PR. A PR that breaks any gate is visibly red instead of merging silently.

**Why this priority**: This is the entire feature. Test discipline is currently enforced only by
convention; one automated gate per PR is the minimum viable product and delivers all of the value.

**Independent Test**: Open a PR that intentionally breaks one gate (e.g. an unformatted file or a
failing unit test) and confirm the corresponding step fails and the overall check is red; open a clean
PR and confirm every step is green.

**Acceptance Scenarios**:

1. **Given** a PR whose code passes lint, formatting, both test suites, and the typecheck, **When** the
   PR is opened or updated, **Then** the CI check runs and reports success.
2. **Given** a PR that introduces an ESLint error, **When** the PR is opened, **Then** the lint step
   fails and the overall check is red.
3. **Given** a PR that introduces an unformatted file, **When** the PR is opened, **Then** the format
   check step fails (and CI does **not** reformat the file).
4. **Given** a PR that introduces a failing TypeScript or Python test, **When** the PR is opened,
   **Then** the corresponding test step fails.
5. **Given** a PR that introduces a TypeScript type error, **When** the PR is opened, **Then** the
   typecheck/build step fails.

---

### User Story 2 - Maintainer can require the check on `main` (Priority: P2)

A maintainer can mark the CI check as a required status check on the `main` branch so that no PR merges
while it is red.

**Why this priority**: Branch protection is a one-time GitHub setting the maintainer applies once the
workflow is green; it is enabled by, but not part of, the workflow file.

**Independent Test**: After the workflow runs green once, the check name appears in the repo's branch
protection "require status checks" list and can be selected.

**Acceptance Scenarios**:

1. **Given** the workflow has run at least once, **When** the maintainer opens branch protection
   settings for `main`, **Then** the CI check is selectable as a required check.

---

### Edge Cases

- **Hermetic Python suite**: the Python tests must run with no network, no Cloudflare `wrangler`, no D1
  database state, and no Playwright browsers. If any test reaches for those, the **test** is fixed, not
  the workflow.
- **Format check must not mutate**: the format step is read-only (`--check`); it never writes the tree.
  Files already excluded by `.prettierignore` (lockfiles, generated files, `.claude`, `specs`, build
  output) are not flagged.
- **Stray local build artifacts** (e.g. a `.next.broken.*` directory left by a failed local build) must
  not be flagged in CI; a fresh checkout never contains them, and they are also ignored locally.
- **Concurrent pushes**: a newer push to the same PR supersedes an in-flight run rather than running
  both to completion.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: A single workflow file under `.github/workflows/` MUST run on `pull_request` and on
  `push` to the `main` branch.
- **FR-002**: The workflow MUST run these as separate, individually visible steps: (a) ESLint
  (`pnpm lint`), (b) a read-only Prettier check, (c) the TypeScript test suite (`pnpm test:ts`),
  (d) the Python test suite (`pnpm test:py`), and (e) a TypeScript typecheck or Next.js build.
- **FR-003**: A `format:check` package script MUST be added that runs Prettier in read-only check mode
  over the repo; the workflow MUST invoke it. CI MUST NOT auto-format or commit any change.
- **FR-004**: The workflow MUST pin the toolchain: Node 22 and the repo's pinned pnpm version (read from
  `package.json`/the lockfile), plus `uv` with Python 3.12.
- **FR-005**: The workflow MUST cache dependencies for both ecosystems (the pnpm store and the `uv`
  environment) so repeat runs are faster.
- **FR-006**: The Python suite MUST stay hermetic (stdlib `unittest`, no `wrangler`/D1/Playwright). Any
  test that violates this MUST be fixed at the test level.
- **FR-007**: A failure in any step MUST fail the overall check; all gates MUST run such that a single
  red check is sufficient to block a non-conforming PR.
- **FR-008**: The repository MUST be in a state where every gate passes on the default branch at the time
  this feature merges (any pre-existing format/lint violations are corrected as part of the work).
- **FR-009**: The workflow MUST be a single file with no build matrix and MUST NOT perform any
  deploy/release/publish action.

### Key Entities

- **CI workflow**: the GitHub Actions YAML file; triggers (`pull_request`, `push` to `main`), the
  pinned toolchain, dependency caches, and the ordered quality-gate steps.
- **`format:check` script**: a package.json script invoking Prettier in `--check` (read-only) mode.
- **`typecheck` script**: a package.json script invoking `tsc --noEmit` (used by the workflow in place
  of a full `next build`, per the issue's allowance).

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 100% of new pull requests trigger the CI check automatically, with no manual action by the
  author.
- **SC-002**: A PR that breaks any one of the five gates produces a red check; a clean PR produces a
  green check (verified by the acceptance scenarios).
- **SC-003**: Each of the five gates is visible as its own named step in the run, so a failure points
  directly at which gate failed.
- **SC-004**: The Python suite completes with zero external dependencies (no network, `wrangler`, D1, or
  Playwright) in the CI environment.
- **SC-005**: Repeat runs reuse cached dependencies (a warm run installs no packages from the network
  beyond cache restoration).

## Assumptions

Recorded because this feature was specified unattended (no clarifying questions asked):

- **A-01 (typecheck over full build)**: The issue explicitly allows `tsc --noEmit` as a faster
  alternative to `pnpm build`. The full `next build` requires OpenNext/Cloudflare context and is far
  slower; we add a `typecheck` script (`tsc --noEmit`) and run **that** as the build/type gate. The
  existing `build` script is left unchanged.
- **A-02 (single check job)**: All five gates run as steps in one job (one workflow, no matrix), so a
  single required status check covers them. Dependencies are installed once and reused across steps.
- **A-03 (toolchain versions)**: Node 22 (matches the dev container and `@types/node` major intent),
  pnpm pinned to the version in the lockfile/dev environment (pnpm 11; lockfile is v9.0 format), `uv`
  with Python 3.12 (matches `scripts/pyproject.toml` `requires-python >=3.12`).
- **A-04 (pre-existing format violation)**: `CLAUDE.md` is currently missing a trailing newline and
  fails `prettier --check`. It is corrected as part of FR-008 so the new gate is green on merge. No
  other tracked file fails any gate.
- **A-05 (Python deps for tests)**: `scripts/pyproject.toml` lists `playwright`/`python-dotenv` as
  project deps, but the **test** suite imports only the stdlib. To keep CI hermetic and fast, the
  Python step installs only what the tests need (it does not install Playwright browsers); `uv run`
  against the project is sufficient since the imported test modules don't load those packages.
- **A-06 (stray-artifact ignore)**: `.next.broken.*` directories (left by failed local builds) are
  added to `.prettierignore`/`.gitignore` so they don't pollute local `format:check`; they never exist
  in a fresh CI checkout.
- **A-07 (concurrency)**: A concurrency group keyed on the workflow + ref cancels superseded in-progress
  runs to save CI minutes.
- **A-08 (branch protection)**: Marking the check as required on `main` is a maintainer GitHub-settings
  action documented for the maintainer; it is out of scope for the workflow file itself.
