# Contract: CI workflow gate

The pipeline's observable contract — what a consumer (PR author / maintainer / branch protection)
can rely on.

## Trigger contract

- Opening or updating a pull request (any base branch) → the `CI` check runs.
- Pushing a commit to `main` → the `CI` check runs.
- No other event triggers it. No scheduled or manual-only runs required.

## Step visibility contract

The run exposes exactly these named gate steps, each independently pass/fail:

| Step name | Command | Read-only? | Pass condition |
|-----------|---------|-----------|----------------|
| Lint | `pnpm lint` | yes | ESLint reports no errors |
| Format check | `pnpm format:check` | yes (never writes) | `prettier --check .` finds no unformatted file |
| TypeScript tests | `pnpm test:ts` | yes | `node --test "src/**/*.test.mjs"` all pass |
| Python tests | `pnpm test:py` | yes | stdlib `unittest` discover under `scripts/` all pass |
| Typecheck | `pnpm typecheck` | yes | `tsc --noEmit` reports no type error |

## Outcome contract

- The job conclusion is the single status check surfaced on the PR (FR-007): any failing gate → the
  check is red; all gates green → the check is green.
- The workflow makes **no** commits, pushes, deploys, or releases (FR-009). `permissions: contents:
  read` guarantees it cannot write to the repo.
- A fresh push to the same ref cancels an in-progress run for that ref (concurrency).

## Hermeticity contract (Python step)

- Runs with `uv` against `scripts/`; requires **no** network, `wrangler`, D1 state, or Playwright
  browsers (FR-006 / SC-004).

## Acceptance mapping

| Spec acceptance scenario | How this contract verifies it |
|---|---|
| US1-1 clean PR green | all five gates pass on a clean PR |
| US1-2 lint error red | Lint step exits non-zero |
| US1-3 unformatted file red, no rewrite | Format check exits non-zero; step is read-only |
| US1-4 failing test red | TypeScript tests / Python tests step exits non-zero |
| US1-5 type error red | Typecheck step exits non-zero |
| US2-1 requirable check | a completed run registers the `CI` check for branch protection |
