# Phase 1 Data Model: CI pipeline

This feature persists no application data. The "entities" are configuration artifacts.

## Entity: CI workflow (`.github/workflows/ci.yml`)

| Field | Value / Rule |
|-------|--------------|
| `name` | `CI` |
| triggers | `pull_request` (all branches); `push` to `main` |
| `permissions` | `contents: read` (least privilege) |
| `concurrency` | group `${{ github.workflow }}-${{ github.ref }}`, `cancel-in-progress: true` |
| jobs | exactly one: `verify`, `runs-on: ubuntu-latest` |
| matrix | none |
| deploy/release steps | none |

### Ordered steps (job `verify`)

1. Checkout (`actions/checkout@v4`)
2. Install pnpm (`pnpm/action-setup@v4`, version 11)
3. Setup Node 22 (`actions/setup-node@v4`, `cache: pnpm`)
4. `pnpm install --frozen-lockfile`
5. Setup `uv` + Python 3.12 (`astral-sh/setup-uv@v5`, `enable-cache: true`, `python-version: 3.12`)
6. **Lint** — `pnpm lint`
7. **Format check** — `pnpm format:check`
8. **TypeScript tests** — `pnpm test:ts`
9. **Python tests** — `pnpm test:py`
10. **Typecheck** — `pnpm typecheck`

Each gate (steps 6–10) is its own named step. Steps run sequentially; default `fail-fast` of a job
means a failed step fails the job, and the job's conclusion is the single check reported on the PR
(FR-007). (Lint/format/test/typecheck are independent; ordering is for readability, not dependency.)

## Entity: `format:check` package script

| Field | Value |
|-------|-------|
| name | `format:check` |
| command | `prettier --check .` |
| mutation | none (read-only); exits non-zero if any file would be reformatted |

## Entity: `typecheck` package script

| Field | Value |
|-------|-------|
| name | `typecheck` |
| command | `tsc --noEmit` |
| mutation | none; exits non-zero on any type error |

## Edits to existing config (not new entities)

- `CLAUDE.md`: add trailing newline (prettier compliance).
- `.prettierignore`: add `.next.broken.*` line.
- `.gitignore`: add `.next.broken.*` line.
