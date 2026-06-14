---
name: ci-split-workflow-path-gating
description: CI is two workflows — ci.yml (verify, every PR+push) and ci-e2e.yml (heavy e2e, push:main always + PR path-gated); native paths, not dorny/paths-filter
metadata:
  type: project
---

CI lives in TWO GitHub Actions workflows (since feature 064 / CI-001 / issue #110):
- `.github/workflows/ci.yml` — the fast `verify` job (lint/format/tests/typecheck). Runs on every `pull_request` and every push to `main`. Unconditional.
- `.github/workflows/ci-e2e.yml` — the heavy `e2e` job (seeded local Miniflare D1/R2 integration + browser smoke, ~32 min). Runs on `push: branches:[main]` (no `paths` → ALWAYS) and `pull_request: paths:[scripts/**, src/**, drizzle/**, wrangler.toml, package.json, pnpm-lock.yaml, .github/workflows/ci-e2e.yml]`. `timeout-minutes: 45`.

**Why:** doc-only / `.claude/`-only / `*.md`-only PRs were paying ~32 min for the e2e suite though nothing they changed could affect it. Native `on.pull_request.paths` (approach B) was chosen over `dorny/paths-filter` (approach A): no third-party action, and a non-matching PR simply does not trigger the workflow (no check at all) instead of a "skipped" status that can block a required check. Top-level `on.paths` on a single ci.yml can't be used — it would gate `verify` too.

**How to apply:** When adding a file type/path whose changes should re-trigger the e2e suite on PRs, append its glob to `ci-e2e.yml`'s `on.pull_request.paths`. `main` always runs e2e regardless (the push trigger has no paths). The two workflows have DISTINCT concurrency groups (`CI-<ref>` vs `ci-e2e-<ref>`) so they don't cancel each other. No GitHub branch protection exists on this repo (merges are approval-hook-gated), so a skipped e2e never blocks merge. See [[prettier-docs-ci-gate]] — the verify job still runs `prettier --check .` over everything.
