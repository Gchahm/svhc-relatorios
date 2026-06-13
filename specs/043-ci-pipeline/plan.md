# Implementation Plan: CI pipeline — lint, format check, both test suites, build

**Branch**: `043-ci-pipeline` | **Date**: 2026-06-12 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/043-ci-pipeline/spec.md`

## Summary

Add a single GitHub Actions workflow (`.github/workflows/ci.yml`) that runs on `pull_request` and on
`push` to `main`, executing five separate, visible quality gates in one job: ESLint, a read-only
Prettier check, the TypeScript test suite, the Python test suite, and a TypeScript typecheck. Add the
two missing package scripts (`format:check`, `typecheck`), pin the toolchain (Node 22 + pnpm, `uv` +
Python 3.12) with dependency caching, and correct the one pre-existing format violation (`CLAUDE.md`)
so the gate is green on merge. No deploy/release automation; one file, no matrix.

## Technical Context

**Language/Version**: YAML (GitHub Actions); Node.js 22 (TS toolchain); Python 3.12 (analysis tests).  
**Primary Dependencies**: GitHub Actions (`actions/checkout@v4`, `pnpm/action-setup@v4`,
`actions/setup-node@v4`, `astral-sh/setup-uv@v5`); existing repo dev deps (`next`/eslint, `prettier`,
`typescript`); `uv` for the Python suite.  
**Storage**: N/A — verification-only pipeline; reads no D1/R2, writes nothing.  
**Testing**: existing `node --test "src/**/*.test.mjs"` (26 tests) and stdlib `unittest` under
`scripts/tests` (133 tests). The workflow's own "tests" are the acceptance scenarios run against the
live pipeline.  
**Target Platform**: GitHub-hosted `ubuntu-latest` runner.  
**Project Type**: Web app (Next.js 15) + Python analysis scripts — single repo, single CI job.  
**Performance Goals**: Warm runs reuse cached deps; the gate completes in a few minutes (typecheck
chosen over full `next build` for speed).  
**Constraints**: One workflow file, no matrix, no deploy. Python suite must stay hermetic (stdlib only;
no network/`wrangler`/D1/Playwright). Prettier step is read-only.  
**Scale/Scope**: 1 workflow file, 2 new package scripts, ~3 small hygiene edits
(`CLAUDE.md` newline, `.prettierignore`/`.gitignore` stray-artifact ignore).

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- **I. Type Safety & Schema Discipline** — REINFORCED. The new `typecheck` gate (`tsc --noEmit`) makes
  the "code MUST type-check cleanly" rule machine-enforced on every PR. No schema/migration/auth-schema
  change.
- **II. Cloudflare-Native Architecture** — N/A. No DB access, no bindings, no build-time/runtime path
  change. We deliberately run `tsc --noEmit` (not a Workers build) so CI needs no Cloudflare context.
- **III. Quality Gates Before Commit** — DIRECTLY SERVED. This feature *is* the automation of the
  lint + format gate the constitution already mandates, extended to the (present, must-pass) test
  suites. Fully aligned.
- **IV. Security & Auth by Default** — N/A to app surface. Workflow has read-only default permissions,
  uses no secrets, and performs no deploy. No new public route.
- **V. Simplicity & Incremental Delivery** — HONORED. One file, one job, no matrix, no new runtime
  dependency. Two tiny package scripts and three hygiene edits. YAGNI: typecheck over full build,
  per the issue's own allowance.

**Result**: PASS. No violations; Complexity Tracking not required.

## Project Structure

### Documentation (this feature)

```text
specs/043-ci-pipeline/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output (workflow/script "entities")
├── quickstart.md        # Phase 1 output (how to run gates locally)
├── contracts/
│   └── ci-workflow.md   # The gate contract (triggers, steps, exit semantics)
└── tasks.md             # Phase 2 output (speckit tasks)
```

### Source Code (repository root)

```text
.github/
└── workflows/
    └── ci.yml           # NEW — the single CI workflow

package.json             # EDIT — add "format:check" and "typecheck" scripts
.prettierignore          # EDIT — ignore ".next.broken.*" stray artifacts
.gitignore               # EDIT — ignore ".next.broken.*" stray artifacts
CLAUDE.md                # EDIT — add trailing newline (pre-existing prettier violation)
```

No `src/` or `scripts/` application code changes are expected (the Python suite is already hermetic —
verified: the only mentions of playwright/wrangler/dotenv in `scripts/tests/` are comments/strings,
not imports).

**Structure Decision**: Single repo, single CI job. The workflow lives in the conventional
`.github/workflows/` directory; package scripts are added to the existing root `package.json`.

## Complexity Tracking

> No constitution violations. Section intentionally empty.
