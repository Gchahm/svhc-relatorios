# Tasks: CI pipeline — lint, format check, both test suites, build

**Feature**: 043-ci-pipeline | **Spec**: [spec.md](./spec.md) | **Plan**: [plan.md](./plan.md)

Tests are NOT separately generated as code: the deliverable *is* a test pipeline; its acceptance is
verified by running the gate commands locally (T009) and by the live GitHub Actions run on the PR.

## Phase 1: Setup (repo cleanliness — prerequisite for a green gate, FR-008)

- [x] T001 Add a trailing newline to `CLAUDE.md` so `prettier --check` passes (the sole tracked file
      currently failing). File: `CLAUDE.md`.
- [x] T002 [P] Add `.next.broken.*` to `.prettierignore` so stray failed-build dirs don't pollute the
      local format check. File: `.prettierignore`.
- [x] T003 [P] Add `.next.broken.*` to `.gitignore`. File: `.gitignore`.

## Phase 2: Foundational (package scripts the workflow invokes — blocks US1)

- [x] T004 Add `"format:check": "prettier --check ."` to the `scripts` block of `package.json`
      (read-only; mirrors the existing `format` write script). File: `package.json`.
- [x] T005 Add `"typecheck": "tsc --noEmit"` to the `scripts` block of `package.json`. File:
      `package.json`.

## Phase 3: User Story 1 — PR author gets automatic verification (Priority: P1) 🎯 MVP

**Goal**: One workflow runs all five gates on every PR and push to `main`, single red/green check.

**Independent Test**: Open a PR; confirm the `CI` check runs with five named steps and is green on a
clean PR / red when any gate breaks.

- [x] T006 Create `.github/workflows/ci.yml`: `name: CI`; triggers `pull_request` and `push` to
      `main`; `permissions: contents: read`; `concurrency` group
      `${{ github.workflow }}-${{ github.ref }}` with `cancel-in-progress: true`; one job `verify` on
      `ubuntu-latest`. File: `.github/workflows/ci.yml`.
- [x] T007 In `verify`, add the setup steps in order: `actions/checkout@v4`; `pnpm/action-setup@v4`
      (version 11); `actions/setup-node@v4` (node-version 22, `cache: pnpm`);
      `pnpm install --frozen-lockfile`; `astral-sh/setup-uv@v5` (`enable-cache: true`,
      `python-version: "3.12"`). File: `.github/workflows/ci.yml`.
- [x] T008 In `verify`, add the five named gate steps in order, each its own step: `Lint`
      (`pnpm lint`), `Format check` (`pnpm format:check`), `TypeScript tests` (`pnpm test:ts`),
      `Python tests` (`pnpm test:py`), `Typecheck` (`pnpm typecheck`). File: `.github/workflows/ci.yml`.

## Phase 4: Verification & Polish

- [x] T009 Locally run every gate command and confirm exit 0: `pnpm lint`, `pnpm format:check`,
      `pnpm test:ts`, `pnpm test:py`, `pnpm typecheck` (or the `node_modules/.bin/*` equivalents per
      quickstart). Record results for the PR body.
- [x] T010 [P] Validate the workflow YAML parses:
      `python -c "import yaml; yaml.safe_load(open('.github/workflows/ci.yml'))"`, and confirm
      `format:check` + `typecheck` exist in `package.json`.
- [x] T011 [P] Confirm the Python suite is hermetic: re-grep `scripts/tests/` for real imports of
      `playwright`/`wrangler`/`dotenv` (expect none — only comments/strings). No test change needed
      unless a real import is found (then fix the test, per FR-006).

## Dependencies

- T001–T003 (setup) and T004–T005 (scripts) before T008 (workflow steps call the scripts) and before
  T009 (local gate run depends on green repo + new scripts).
- T006 → T007 → T008 are sequential edits to the same file.
- T009/T010/T011 after the workflow + scripts exist.

## Parallel opportunities

- T002, T003 are independent files → parallel.
- T010, T011 are independent checks → parallel.

## Implementation strategy

MVP = US1 (the workflow). Setup + Foundational are tiny prerequisites that make the gate green on
merge. There is one user story; ship it whole.
