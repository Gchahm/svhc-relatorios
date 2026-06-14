# Research: Gate the CI e2e job on PRs by changed paths

## Decision 1 — Gating mechanism: native `paths` (split workflow) vs `dorny/paths-filter`

- **Decision**: Use GitHub-native `on.pull_request.paths` filtering by moving the `e2e` job into its own workflow file `ci-e2e.yml` (issue approach B).
- **Rationale**:
  - No third-party dependency (constitution V — simplicity / YAGNI). `dorny/paths-filter` would add a pinned external action and an extra `changes` pre-job.
  - GitHub evaluates `on.<event>.paths` before scheduling the workflow, so a non-matching PR produces **no** `e2e` run/check at all — sidestepping the "skipped job still reports a status" required-check gotcha entirely.
  - `on.pull_request.paths` cannot be used at the top of `ci.yml` because it would gate the **whole** workflow including `verify`, which must always run. Splitting lets each workflow have its own `on:`.
- **Alternatives considered**:
  - **(A) `dorny/paths-filter` pre-job + job-level `if:`** — works, but adds a dependency, an extra job, and yields a "skipped" status that can block required-check branch protection. Rejected.
  - **Top-level `paths` on the single `ci.yml`** — would also gate `verify`. Rejected (violates FR-005).

## Decision 2 — `main` always runs e2e

- **Decision**: `on.push.branches: [main]` with **no** `paths` filter on the push trigger.
- **Rationale**: Omitting `paths` on a trigger means "match any change". So every push to `main` runs `e2e` regardless of touched paths (FR-004 / SC-003). `pull_request` keeps its `paths` filter; the two triggers are independent.

## Decision 3 — Concurrency

- **Decision**: Give `ci-e2e.yml` its own `concurrency` block, group `ci-e2e-${{ github.ref }}`, `cancel-in-progress: true`.
- **Rationale**: Preserve the existing "newer push supersedes in-flight run" behavior for the e2e workflow. A **distinct** group name from `ci.yml`'s (`${{ github.workflow }}-${{ github.ref }}` → `CI-<ref>`) ensures the two workflows don't cancel each other — each supersedes only its own runs.

## Decision 4 — `timeout-minutes`

- **Decision**: `timeout-minutes: 45` on the `e2e` job.
- **Rationale**: The suite runs ~32 min; 45 gives ~40% headroom for a slow-but-healthy run while still capping a genuine hang (FR-006 / SC-004). A round, generous value avoids flaky cancellations.

## Decision 5 — Relevant paths set

- **Decision**: `scripts/**`, `src/**`, `drizzle/**`, `wrangler.toml`, `package.json`, `pnpm-lock.yaml`, `.github/workflows/ci-e2e.yml`.
- **Rationale**: These are the only paths whose changes can alter what the integration/e2e suite exercises: the pipeline/test code (`scripts/**`), the app (`src/**`), schema/migrations (`drizzle/**`), the Workers/binding config (`wrangler.toml`), deps + lockfile (`package.json`, `pnpm-lock.yaml`), and the e2e workflow itself (A4 — so changes to the gating are exercised). Doc/agent paths (`**/*.md`, `.claude/**`, `docs/**`) are excluded by omission (a `pull_request.paths` allowlist runs only on a match), satisfying FR-003 without an explicit `paths-ignore`.
- **Note**: `drizzle.config.ts` and `wrangler.json`/`open-next.config.ts` are not separately listed; `wrangler.toml` is the binding source the e2e build reads, and migrations live in `drizzle/**`. If a future config file proves load-bearing for e2e it can be appended — out of scope here.
