# Contract: `SVHC_WRANGLER_PERSIST` persist selector

This feature has no HTTP/API surface. Its contract is the behavior of the persist selector across the
wrangler shell-outs and npm scripts.

## `_persist_args(target)` (scripts/common/d1.py)

| `target` | `SVHC_WRANGLER_PERSIST` | Result |
|----------|-------------------------|--------|
| `"local"` | unset | `[]` (wrangler default `.wrangler/state`) |
| `"local"` | `""` (empty) | `[]` (treated as unset) |
| `"local"` | `".wrangler/state-test"` (relative) | `["--persist-to", "<repo>/.wrangler/state-test"]` |
| `"local"` | `"/abs/dir"` (absolute) | `["--persist-to", "/abs/dir"]` |
| `"remote"` | `".wrangler/state-test"` | `[]` (remote NEVER redirected) |
| `"remote"` | unset | `[]` |

Applied to: `execute_sql`, `query`, `put_object`, `get_object` — appended to the wrangler argv after
the existing flags.

## npm scripts

| Script | Selector / flag | Target DB |
|--------|-----------------|-----------|
| `test:py:integration` | `SVHC_WRANGLER_PERSIST=.wrangler/state-test` prefix | test |
| `e2e:seed` | `SVHC_WRANGLER_PERSIST=.wrangler/state-test` prefix | test |
| `e2e:smoke` | `SVHC_WRANGLER_PERSIST=.wrangler/state-test` prefix | test |
| `test:e2e` | `SVHC_WRANGLER_PERSIST=.wrangler/state-test` prefix | test |
| `db:migrate:test` | explicit `--persist-to .wrangler/state-test` | test |
| `preview:test` | explicit `-- --persist-to .wrangler/state-test` | test |
| `dev` | none | staging (default) — UNCHANGED |
| `preview` | none | staging (default) — UNCHANGED |
| `db:migrate:dev` | none | staging (default) — UNCHANGED |
| `db:studio:dev` | none | staging (default) — UNCHANGED |

## server.py (browser smoke preview)

When `SVHC_WRANGLER_PERSIST` is set, `serve()` appends `--persist-to <resolved dir>` to the
`pnpm preview -- --port <port>` argv (forwarded to the underlying `wrangler dev`), so the served
Worker reads the test DB. When unset, the preview serves staging (today's behavior).

## Invariants

- Selector unset ⇒ every command is byte-identical to today (SC-001).
- `--remote` is never given `--persist-to` (SC-005).
- The test suites read/write only `.wrangler/state-test`; staging rows are untouched (SC-003).
