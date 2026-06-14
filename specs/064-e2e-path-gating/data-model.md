# Data Model: Gate the CI e2e job on PRs by changed paths

This feature introduces no application data entities, no D1 schema, and no persisted state. The only "entities" are CI workflow configuration objects.

## Configuration entities

### Workflow: `ci.yml` (modified)

| Field | Value |
|-------|-------|
| `name` | `CI` (unchanged) |
| `on.pull_request` | `{}` (every PR — unchanged) |
| `on.push.branches` | `[main]` (unchanged) |
| `permissions.contents` | `read` (unchanged) |
| `concurrency.group` | `${{ github.workflow }}-${{ github.ref }}` (unchanged) |
| jobs | `verify` only (the `e2e` job is removed) |

### Workflow: `ci-e2e.yml` (new)

| Field | Value |
|-------|-------|
| `name` | `CI e2e` |
| `on.push.branches` | `[main]` (no `paths` → always on main) |
| `on.pull_request.paths` | `[scripts/**, src/**, drizzle/**, wrangler.toml, package.json, pnpm-lock.yaml, .github/workflows/ci-e2e.yml]` |
| `permissions.contents` | `read` |
| `concurrency.group` | `ci-e2e-${{ github.ref }}` |
| `concurrency.cancel-in-progress` | `true` |
| jobs | `e2e` only — moved verbatim from `ci.yml`, plus `timeout-minutes: 45` |

## State / transitions

The "trigger decision" is computed by GitHub from the event + changed-file set, not stored:

| Event | Changed paths | `verify` runs? | `e2e` runs? |
|-------|---------------|----------------|-------------|
| `pull_request` | only docs/`.claude`/`*.md` | yes | no |
| `pull_request` | ≥1 of relevant set | yes | yes |
| `pull_request` | mix (relevant + docs) | yes | yes |
| `push` to `main` | any | yes | yes |
