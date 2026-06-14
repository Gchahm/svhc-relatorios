# Implementation Plan: Gate the CI e2e job on PRs by changed paths

**Branch**: `064-e2e-path-gating` | **Date**: 2026-06-14 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/064-e2e-path-gating/spec.md`

## Summary

Split the heavy `e2e` job out of `.github/workflows/ci.yml` into its own workflow `.github/workflows/ci-e2e.yml`, triggered by `on.push.branches: [main]` (unconditional full coverage on main) and `on.pull_request.paths: [<functional paths>]` (GitHub-native path gating, so a doc-only/`.claude/`-only PR skips it). Add `timeout-minutes` to the `e2e` job. `ci.yml` keeps only the `verify` job, which continues to run on every PR and every push to main. No job *steps* change — the `e2e` job's steps are moved verbatim.

## Technical Context

**Language/Version**: GitHub Actions workflow YAML (no app language change)
**Primary Dependencies**: GitHub Actions native `on.pull_request.paths` / `on.push.branches` filtering — no third-party action (no `dorny/paths-filter`)
**Storage**: N/A
**Testing**: Static validation — YAML parse + `actionlint` if available; semantic reasoning over trigger rules. The jobs' own steps (which run the integration/e2e suites) are unchanged.
**Target Platform**: GitHub Actions CI (ubuntu-latest runners)
**Project Type**: web (Next.js on Cloudflare) — but this feature touches only CI config, no `src/`
**Performance Goals**: Doc-only PRs no longer pay the ~32 min e2e cost; functional PRs and all `main` pushes keep full coverage.
**Constraints**: No D1 schema, app-code, or test-code change (FR-008). `verify` unchanged (FR-005).
**Scale/Scope**: Two workflow files; one moved job; one added `timeout-minutes`.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- **I. Type Safety & Schema Discipline** — N/A. No schema, no TypeScript, no auth-config change.
- **II. Cloudflare-Native Architecture** — N/A. No DB/binding code touched; the e2e job's Miniflare/wrangler steps are moved verbatim.
- **III. Quality Gates Before Commit** — PASS. The `verify` job (lint/format/tests/typecheck) is preserved unchanged and still runs on every PR and push. Prettier covers `.github/**/*.yml`? Prettier's default ignores nothing here, so run `pnpm format` on the YAML before committing to avoid a format-check failure.
- **IV. Security & Auth by Default** — PASS. CI `permissions: contents: read` is preserved on both workflows; no secrets added. The e2e workflow injects no new secrets (the throwaway `BETTER_AUTH_SECRET` is generated at runtime by `server.py`, unchanged).
- **V. Simplicity & Incremental Delivery** — PASS. Approach (B), native path filtering, is the simplest option: no new dependency (rejects `dorny/paths-filter`), no extra pre-job, no `if:` expression gymnastics. YAGNI honored.

**Result**: No violations. Complexity Tracking empty.

## Project Structure

### Documentation (this feature)

```text
specs/064-e2e-path-gating/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output (minimal — no data entities)
├── quickstart.md        # Phase 1 output
├── contracts/           # Phase 1 output (trigger-matrix contract)
└── tasks.md             # Phase 2 output (speckit tasks)
```

### Source Code (repository root)

```text
.github/workflows/
├── ci.yml         # MODIFIED: drop the `e2e` job; keep `verify` (+ its on: pull_request / push:main)
└── ci-e2e.yml     # NEW: the `e2e` job, with on: { push: {branches:[main]}, pull_request: {paths:[…]} }
                   #      + concurrency block + timeout-minutes
```

**Structure Decision**: This is a CI-configuration-only change. No `src/`, `scripts/`, or `drizzle/` files are touched. Two files under `.github/workflows/` change.

## Design notes

### Gating approach (B) — split workflow

- **`ci.yml`** retains `name: CI`, `on: { pull_request: {}, push: { branches: [main] } }`, `permissions: contents: read`, the `concurrency` block, and the single `verify` job. The `e2e` job block (lines 69–119 of the current file) is removed.
- **`ci-e2e.yml`** is a new workflow holding the `e2e` job verbatim (same `name`, `runs-on`, all steps), plus:
  - `on:`
    - `push: { branches: [main] }` — unconditional on main (FR-004).
    - `pull_request: { paths: [scripts/**, src/**, drizzle/**, wrangler.toml, package.json, pnpm-lock.yaml, .github/workflows/ci-e2e.yml] }` — gated on PRs (FR-001/FR-002/FR-003/A4). GitHub treats omitting `paths` on `push` as "always", and a `pull_request` with `paths` runs only when ≥1 changed file matches.
  - `permissions: contents: read` (mirror ci.yml).
  - `concurrency: { group: ci-e2e-${{ github.ref }}, cancel-in-progress: true }` (A3 — its own group so it supersedes its own in-flight runs; distinct group name from ci.yml so the two workflows don't cancel each other).
  - `timeout-minutes: 45` on the `e2e` job (FR-006).

### Required-check handling (FR-007 / A1)

No GitHub branch protection exists today (verified: `gh api .../branches/main/protection` → 404); merge is approval-gated by a project hook. A skipped `e2e` therefore cannot block a merge. With the split-workflow approach, a PR that skips `e2e` simply has no `Integration + E2E smoke` check at all (the workflow doesn't trigger), rather than a "skipped" check — this is the cleanest required-check story: `verify` is the always-present PR gate; `e2e` is the gate on main and on functional PRs. Documented in the PR; no "always-run gate job" needed.

### Why not approach (A) — `dorny/paths-filter` pre-job

Rejected per A2: it adds a third-party action + an extra `changes` job + an `if:` expression on `e2e`, and produces a "skipped" status (the required-check gotcha) rather than simply not triggering. Native `paths` is simpler and avoids the gotcha entirely.

## Complexity Tracking

> No Constitution Check violations — table intentionally empty.
