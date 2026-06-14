# Phase 0 Research: Isolated local test database

## R1 — Mechanism for local DB isolation

**Decision**: Use wrangler's per-invocation `--persist-to <dir>` flag, selected by an env var
`SVHC_WRANGLER_PERSIST`. Test dir = `.wrangler/state-test`; unset ⇒ wrangler default `.wrangler/state`.

**Rationale**: `wrangler … --persist-to <dir>` co-locates that invocation's local D1 + R2 + KV state
in one directory (verified: `wrangler dev`, `wrangler d1 execute`, and `wrangler d1 migrations apply`
all accept `--persist-to`). An env var (vs a threaded function arg) propagates through a single
high-level call's fan-out to dozens of `d1.py` shell-outs and through nested `subprocess`
invocations without touching every signature.

**Alternatives considered**:
- A second `[[d1_databases]]` binding / second `database_name` in `wrangler.toml` — rejected (NFR-002):
  the app reads the single `DATABASE` binding; a second binding forces env-driven binding selection
  in app code, violating "no `src/` change."
- Threading a `persist_dir` arg through `d1.py` and every caller — rejected: a full analysis run fans
  out to dozens of calls and nested subprocesses; an env var is the one seam that reaches all of them.

## R2 — Where the env var is read

**Decision**: Read it once in a pure helper `_persist_args(target) -> list[str]` in
`scripts/common/d1.py`. Returns `["--persist-to", <resolved abs dir>]` only when `target == "local"`
AND `SVHC_WRANGLER_PERSIST` is set; otherwise `[]`.

**Rationale**: `d1.py` is the single home of every Python→wrangler local shell-out (execute/query/R2
put/get). One helper appended to all four call sites keeps them consistent and guarantees `--remote`
is never redirected (FR-003) and unset ⇒ no flag (FR-002, byte-identical to today).

**Resolution rule**: A relative selector value resolves against `_REPO_ROOT` (already defined in
`d1.py`), since wrangler runs with `cwd = _REPO_ROOT` but npm scripts run from `scripts/` — resolving
against the repo root makes the dir stable regardless of process CWD (FR-004). An already-absolute
value is used as-is.

## R3 — Serving the browser smoke against the test DB

**Decision**: In `scripts/e2e/server.py`, when `SVHC_WRANGLER_PERSIST` is set, forward
`--persist-to <resolved dir>` to the existing `pnpm preview -- --port <port>` invocation (appended
after the existing `--`-delimited flags).

**Rationale**: `opennextjs-cloudflare preview` takes positional `[args..]` that pass through to the
underlying `wrangler dev` (the existing code already relies on this for `--port`). `wrangler dev`
supports `--persist-to`. The env var is set by the `test:e2e` npm script; `server.py` reads it and
resolves it the same way `d1.py` does (relative ⇒ repo root). When unset, the preview behaves as
today (staging) — no regression for the human's `pnpm preview`.

**Alternatives considered**: Have `server.py` set the env var itself — rejected: the served Worker
process needs the flag passed to `wrangler dev` explicitly (the env var alone does not redirect
wrangler's state; only `--persist-to` does), so the flag must be forwarded.

## R4 — Which entrypoints isolate

**Decision**: Prefix `SVHC_WRANGLER_PERSIST=.wrangler/state-test` only on the test/seed/e2e scripts:
`test:py:integration`, `e2e:seed`, `e2e:smoke`, `test:e2e`. All other local scripts (`dev`,
`preview`, `db:migrate:dev`, `db:studio:dev`) are left untouched (= staging default).

**Rationale**: Matches the issue's stated routing decision ("tests isolate; everything else =
staging"). These four call `d1.py` in-process (and, for `test:e2e`, also serve via `server.py`), so
exporting the var for the command propagates to all nested calls — the integration harness and
`e2e/seed.py` need no logic change. The relative value is resolved by `d1.py`/`server.py` against the
repo root, so it works whether the npm script runs from repo root or `scripts/`.

## R5 — New scripts (staging unchanged)

**Decision**:
- `db:migrate:test` — `wrangler d1 migrations apply DATABASE --local --persist-to .wrangler/state-test`
  (bootstraps/migrates the test DB explicitly; no `d1.py`, so it carries the explicit flag).
- `preview:test` — builds + previews against the test DB using the same pass-through form
  `server.py` uses: `opennextjs-cloudflare build && opennextjs-cloudflare preview -- --persist-to .wrangler/state-test`.
- `db:studio:test` (optional nice-to-have) — Drizzle Studio against the test DB's sqlite file under
  `.wrangler/state-test`. Drizzle Studio reads the file path from `drizzle.config`, which already
  points at the Miniflare sqlite under `.wrangler/state`; pointing it at the test dir would require a
  separate config / env switch. **Deferred** (A-005) unless trivially achievable, since it does not
  affect acceptance and the cost/benefit is poor — the human can use `pnpm e2e:seed` + `pnpm preview:test`
  to inspect the test DB.

**Rationale**: Keep the existing scripts byte-identical (FR-010), add discoverable `*:test` siblings
(FR-008, FR-009). `db:migrate:test` carries the explicit `--persist-to` rather than relying on the env
var because `wrangler d1 migrations apply` does not go through `d1.py`.

## R6 — Gitignore

**Decision**: `.gitignore` already has `.wrangler` (line 43), which covers `.wrangler/state-test`.
Verified — no change needed (FR-011 satisfied). The plan notes this so the analyze/PR phases don't
re-add a redundant rule.

## R7 — CI

**Decision**: No CI workflow change is required for the env var to take effect — the `e2e` job runs
the same npm scripts (`test:py:integration`, `e2e:seed`, `e2e:smoke` / `test:e2e`), which now carry
the prefix. The runner is ephemeral, so isolating to `.wrangler/state-test` is behaviorally
equivalent to today (NFR-003). No workflow edit unless a script name the CI invokes changed (it did
not).

## R8 — Drizzle Studio test config + a pre-existing fragility (resolution of R5 optional item)

**Decision**: Defer `db:studio:test`.

**Finding (verified)**: `drizzle.config.ts`'s `getLocalD1DB()` does
`readdirSync(".wrangler", { recursive: true }).find(f => f.endsWith(".sqlite"))` — it returns the
**first** `.sqlite` it encounters anywhere under `.wrangler`, with no path filter (it does not even
target the D1 dir specifically; this is a pre-existing quirk independent of this feature). Adding a
second state dir (`.wrangler/state-test`) introduces more `.sqlite` files under `.wrangler`, which
*could* change which file `db:studio:dev` resolves to — a potential bump against FR-010
("db:studio:dev unchanged").

**Mitigation / scoping**:
- This feature does **not** create `.wrangler/state-test` at rest; it is created on demand by
  `db:migrate:test` / `e2e:seed` / the test suites and is gitignored. On a fresh checkout and for the
  human who never opts into the test scripts, the `.wrangler` tree is identical to today, so
  `db:studio:dev` is unaffected.
- A `db:studio:test` variant would need a parallel drizzle config or a path env switch pointing the
  studio at `.wrangler/state-test`'s sqlite — out of proportion to its value (A-005). The human can
  inspect the seeded test DB via `pnpm e2e:seed` + `pnpm preview:test` instead.
- **Out of scope to fix** the `getLocalD1DB()` first-match quirk itself (it would mean an
  `src/`/config change beyond this feature's dev-tooling boundary; it is a latent pre-existing issue,
  not introduced here). Documented in the quickstart as a known interaction so a future change can
  address it.

**Decision**: Deferred; acceptance does not depend on `db:studio:test`. The interaction is documented,
not silently ignored.
