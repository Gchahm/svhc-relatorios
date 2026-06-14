# Feature Specification: Gate the CI e2e job on PRs by changed paths

**Feature Branch**: `064-e2e-path-gating`
**Created**: 2026-06-14
**Status**: Draft
**Input**: CI-001 (issue #110) — Run the e2e job on PRs only when relevant paths change (keep it on main)

## Overview

The CI pipeline runs a heavy `e2e` job (seeded local D1/R2 integration tests + browser smoke, ~32 min) on **every** pull request. A doc-only, `.claude/`-only, or test-only PR pays that full cost even though nothing it changed can affect the integration/e2e surface, putting the suite on the critical path of every iteration.

This feature gates the `e2e` job so that on a PR it runs **only when relevant (functional) paths changed**, while still running on **every push to `main`** (so `main` keeps full coverage regardless of which paths a merge touched). The fast `verify` job keeps running on every PR and every push unconditionally. A `timeout-minutes` cap is added to `e2e` as a backstop against a runaway run. No change is made to what any job *does* — only to when `e2e` triggers.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Doc-only PR skips e2e (Priority: P1)

A contributor opens a PR that touches only documentation, `.claude/` agent/skill files, or `*.md` files. They expect fast feedback without paying for the integration/browser suite.

**Why this priority**: This is the core value of the feature — removing the heavy suite from the critical path of non-functional PRs.

**Independent Test**: Open a PR changing only `*.md`/`.claude/`/`docs/` files and observe the GitHub Checks view: `e2e` does not run, `verify` does.

**Acceptance Scenarios**:

1. **Given** a PR whose changed files are all under `**/*.md`, `.claude/**`, or `docs/**`, **When** CI runs, **Then** the `e2e` job does **not** run (reports skipped/neutral) and the `verify` job still runs.

---

### User Story 2 - Functional PR runs e2e (Priority: P1)

A contributor opens a PR that touches application or pipeline code, schema/migrations, build config, or dependencies. They expect the full integration/browser suite to run before merge.

**Why this priority**: Functional changes must keep full pre-merge coverage — gating must not create a coverage hole.

**Independent Test**: Open a PR changing a file under `scripts/`, `src/`, `drizzle/`, or `wrangler.toml` and observe that `e2e` runs.

**Acceptance Scenarios**:

1. **Given** a PR that changes any of `scripts/**`, `src/**`, `drizzle/**`, `wrangler.toml`, `package.json`, `pnpm-lock.yaml`, or the CI workflow file(s), **When** CI runs, **Then** the `e2e` job runs to completion.

---

### User Story 3 - main always has full coverage (Priority: P1)

A maintainer merges any PR into `main`. They expect `main` to always be validated by the full suite regardless of which paths the merge touched.

**Why this priority**: `main` is the release surface; it must never lose coverage because a merge happened to touch only doc paths.

**Independent Test**: Push to `main` and observe `e2e` runs unconditionally.

**Acceptance Scenarios**:

1. **Given** a push to `main`, **When** CI runs, **Then** the `e2e` job runs unconditionally (path filter does not apply), and `verify` also runs.

---

### User Story 4 - runaway run is capped (Priority: P2)

A maintainer wants protection against a hung `e2e` run consuming a runner indefinitely.

**Why this priority**: A safety backstop; useful but secondary to the path-gating itself.

**Independent Test**: Inspect the workflow — the `e2e` job declares `timeout-minutes`.

**Acceptance Scenarios**:

1. **Given** the `e2e` job hangs, **When** it exceeds its time budget, **Then** the job is cancelled by a `timeout-minutes` cap rather than running indefinitely.

### Edge Cases

- A PR that touches **both** functional and doc paths runs `e2e` (any relevant-path match triggers it).
- A PR that changes only the CI workflow file itself runs `e2e` (the workflow is a relevant path so its own changes are exercised).
- A skipped `e2e` job must not block merging a legitimately doc-only PR (required-check handling — see Assumptions).

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: On a `pull_request` event, the `e2e` job MUST run if and only if the PR's changed file set intersects the relevant-paths set; otherwise it MUST be skipped.
- **FR-002**: The relevant-paths set (PR triggers e2e) MUST include: `scripts/**`, `src/**`, `drizzle/**`, `wrangler.toml`, `package.json`, `pnpm-lock.yaml`, and the CI workflow file(s) that define the `e2e` job.
- **FR-003**: Changes confined to `**/*.md`, `.claude/**`, and `docs/**` MUST NOT trigger `e2e` on a PR.
- **FR-004**: On a `push` to `main`, the `e2e` job MUST run unconditionally (no path gating).
- **FR-005**: The `verify` job MUST continue to run on every `pull_request` and every push to `main`, unchanged and unconditionally.
- **FR-006**: The `e2e` job MUST have a `timeout-minutes` cap as a backstop against a runaway run.
- **FR-007**: A legitimately skipped `e2e` job MUST NOT block merging the PR (required-check behavior is correct / documented).
- **FR-008**: The steps each job runs (their behavior) MUST be unchanged — only triggering conditions change. No D1 schema, application-code, or test-code change.

### Key Entities *(include if feature involves data)*

- **CI workflow**: the GitHub Actions YAML (`.github/workflows/ci.yml` and/or a sibling `ci-e2e.yml`) defining the `verify` and `e2e` jobs and their trigger/gating conditions.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A PR touching only docs/`.claude/`/`*.md` completes CI without the `e2e` job running, while `verify` runs — confirmed by the GitHub Checks/Actions view.
- **SC-002**: A PR touching `scripts/**` / `src/**` / `wrangler.toml` / a migration runs `e2e`.
- **SC-003**: A push to `main` runs `e2e` regardless of changed paths.
- **SC-004**: The `e2e` job shows a `timeout-minutes` cap in the workflow.
- **SC-005**: A doc-only PR can be merged without `e2e` blocking it.
- **SC-006**: No diff to any job's steps — `git diff` shows only trigger/gating/timeout changes (and any pure-mechanical job restructuring needed to gate cleanly).

## Assumptions

- **A1 — required-check handling**: The repository currently has **no GitHub branch protection** on `main` (`gh api repos/.../branches/main/protection` → 404); merges are approval-gated by a project hook rather than by GitHub required status checks, so a skipped `e2e` cannot block a merge today. To keep FR-007 robust if branch protection is later added, the implementation relies on `verify` as the required gate on PRs and `e2e` as the gate on `main`, documented in the PR. No separate "always-run gate job" is added.
- **A2 — gating approach**: Of the two issue-suggested approaches — (A) a `dorny/paths-filter` pre-job, or (B) splitting `e2e` into its own workflow with native `on.pull_request.paths` + `on.push.branches: [main]` — the implementer chooses approach **(B) split workflow**, because GitHub-native path filtering needs no third-party action, no extra `changes` pre-job, and `paths`/`branches` are evaluated by GitHub before the job is scheduled. `verify` stays in `ci.yml` (runs always); `e2e` moves to a new `ci-e2e.yml`. Recorded in the plan.
- **A3 — concurrency**: The existing `concurrency` group cancels superseded in-flight runs per ref. The split-out `e2e` workflow gets its own equivalent `concurrency` block so a new push still supersedes an in-flight `e2e` run.
- **A4 — relevant paths for the e2e workflow file**: With approach (B), the e2e workflow's own file (`.github/workflows/ci-e2e.yml`) is included in its `on.pull_request.paths` so changes to it are exercised on PRs.
- **A5 — no app-facing surface**: This change is to GitHub Actions YAML; it is verified by static validation (YAML parse / `actionlint` if available) and by reasoning about trigger semantics, not by running the app.

## Dependencies

- None. Independent of the suite-trim and parallelize issues (they compound but are not prerequisites).

## Out of Scope

- Moving `e2e` to nightly-only.
- Reducing the e2e suite's runtime.
- Any change to the jobs' steps or the tests themselves.
