# Contract: CI trigger matrix

The observable contract of this feature is the set of jobs GitHub schedules for a given event. This is verifiable from the GitHub Actions UI / Checks tab on a PR and on `main`.

## Contract

| # | Event | Changed file set | `verify` (ci.yml) | `e2e` (ci-e2e.yml) | Maps to |
|---|-------|------------------|-------------------|--------------------|---------|
| C1 | `pull_request` | `README.md`, `docs/x.md`, `.claude/agents/y.md` only | scheduled | NOT scheduled | FR-001, FR-003, SC-001 |
| C2 | `pull_request` | any `scripts/**` file | scheduled | scheduled | FR-001, FR-002, SC-002 |
| C3 | `pull_request` | any `src/**` file | scheduled | scheduled | FR-002, SC-002 |
| C4 | `pull_request` | `wrangler.toml` or `drizzle/**` migration | scheduled | scheduled | FR-002, SC-002 |
| C5 | `pull_request` | `package.json` / `pnpm-lock.yaml` | scheduled | scheduled | FR-002 |
| C6 | `pull_request` | `.github/workflows/ci-e2e.yml` | scheduled | scheduled | A4 |
| C7 | `pull_request` | mix: `src/a.ts` + `docs/b.md` | scheduled | scheduled | edge case (any match) |
| C8 | `push` to `main` | any (even doc-only) | scheduled | scheduled | FR-004, SC-003 |

## Static invariants (verifiable without triggering a run)

- I1: `ci.yml` contains a `verify` job and **no** `e2e` job. (FR-005, SC-006)
- I2: `ci-e2e.yml` contains an `e2e` job whose steps are byte-identical (modulo indentation/anchoring) to the former `ci.yml` `e2e` steps. (FR-008, SC-006)
- I3: `ci-e2e.yml` `e2e` job declares `timeout-minutes`. (FR-006, SC-004)
- I4: `ci-e2e.yml` `on.pull_request.paths` lists exactly the relevant set; `on.push.branches` is `[main]` with no `paths`. (FR-002, FR-004)
- I5: Both workflows declare `permissions: contents: read`. (security)
- I6: Both workflow files parse as valid YAML / pass `actionlint` if available.
