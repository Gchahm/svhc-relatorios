# Tasks: Gate the CI e2e job on PRs by changed paths

**Feature**: 064-e2e-path-gating | **Spec**: [spec.md](./spec.md) | **Plan**: [plan.md](./plan.md)

This is a CI-configuration-only change (two GitHub Actions YAML files). All four user stories are satisfied by the same split + trigger configuration, so the work is one cohesive edit verified against the trigger matrix.

## Phase 1: Setup

- [ ] T001 Confirm current CI layout by reading `.github/workflows/ci.yml` (the `verify` job, lines ~17–67, and the `e2e` job, lines ~69–119) so the move is byte-faithful.

## Phase 2: Foundational

(none — no shared infrastructure precedes the change.)

## Phase 3: User Story 1 — Doc-only PR skips e2e (P1) + US2/US3 (P1)

These three P1 stories share the same configuration change and are delivered together.

- [ ] T002 [US1] Remove the `e2e` job block from `.github/workflows/ci.yml`, leaving `verify` plus the unchanged top-level `on` (`pull_request` + `push: branches:[main]`), `permissions: contents: read`, and `concurrency` block.
- [ ] T003 [US3] Create new workflow `.github/workflows/ci-e2e.yml` with `name: CI e2e`, `permissions: contents: read`, a `concurrency` block (`group: ci-e2e-${{ github.ref }}`, `cancel-in-progress: true`), and `on: { push: { branches: [main] }, pull_request: { paths: [scripts/**, src/**, drizzle/**, wrangler.toml, package.json, pnpm-lock.yaml, .github/workflows/ci-e2e.yml] } }`.
- [ ] T004 [US2] Move the `e2e` job (all steps verbatim) into `.github/workflows/ci-e2e.yml` under `jobs.e2e`.

## Phase 4: User Story 4 — runaway run is capped (P2)

- [ ] T005 [US4] Add `timeout-minutes: 45` to the `e2e` job in `.github/workflows/ci-e2e.yml`.

## Phase 5: Polish & verification

- [ ] T006 Validate both workflow files parse as YAML and (if `actionlint` is installed) pass `actionlint`.
- [ ] T007 Run `pnpm format` (or `pnpm format:check`) so the new/changed YAML passes the constitution III formatting gate, then `git diff` to confirm `verify` steps are untouched and only trigger/gating/timeout differ (SC-006).
- [ ] T008 Verify against the trigger matrix in `contracts/trigger-matrix.md` by reasoning (and, post-push, by the PR's own Checks tab showing both `CI / verify` and `CI e2e / e2e`).

## Dependencies

- T001 → T002, T003, T004 (read before edit).
- T003 before T004/T005 (file must exist).
- T006/T007/T008 after T002–T005.

## MVP

US1+US2+US3 (T002–T004) form the MVP — the path gating itself. US4 (timeout) is an additive backstop.
