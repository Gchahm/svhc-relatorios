---
name: prettier-docs-ci-gate
description: CI "Lint, format, tests, typecheck" job fails on prettier --check of touched .md docs even when tests/lint pass; run prettier --write before pushing
metadata:
  type: feedback
---

The CI job **"Lint, format, tests, typecheck"** runs `prettier --check .` over the WHOLE repo, including markdown (`docs/**`, `CLAUDE.md`, specs). A PR that only touches docs can pass ESLint + all unit/integration tests locally yet still go red in CI on prettier formatting (markdown table alignment, `*italics*`→`_italics_`, blank line around headings). Observed on PR #95 (issue #84): reviewer verified tests locally, approved, but never ran `prettier --check`, so CI failed on two touched runbook/feature `.md` files.

**Why:** prettier is part of the same CI job as tests, and `prettier --check` covers `.md`; the reviewer/verify steps don't always exercise it.

**How to apply:** before pushing ANY branch — especially doc-only or doc-touching changes — run `node_modules/.bin/prettier --write <changed files>` (or `pnpm format`) and re-`--check`. Pushing a new commit re-mints the head, so any prior `VERDICT: approve` no longer satisfies the merge gate at the new head — you must wait for a fresh reviewer approval at the new head before merging. Use `node_modules/.bin/prettier` directly (see [[db-generate-pnpm-workaround]] in user auto-memory for the pnpm sandbox issue).
