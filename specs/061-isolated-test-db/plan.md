# Implementation Plan: Isolated local test database (separate from the human's staging DB)

**Branch**: `061-isolated-test-db` | **Date**: 2026-06-14 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/061-isolated-test-db/spec.md`

## Summary

Route the agents' automated test/seed/e2e tooling to an isolated Miniflare persist directory
(`.wrangler/state-test`) so it can wipe-and-reseed freely without touching the human's default
local DB (`.wrangler/state` = staging). A single env-var selector (`SVHC_WRANGLER_PERSIST`) is read
by the Python wrangler wrapper (`scripts/common/d1.py`) and appended as `--persist-to <dir>` to every
**local** wrangler shell-out (never for `--remote`). The test/seed/e2e npm scripts export the
selector pointing at the test dir; the browser-smoke preview server forwards `--persist-to` to the
underlying `wrangler dev`. New `*:test` scripts (`db:migrate:test`, `preview:test`, optional
`db:studio:test`) let the human bootstrap/eyeball the test DB. Staging scripts are unchanged.
Dev-environment infra only: no `src/`, no schema, no migration, no `wrangler.toml` change.

## Technical Context

**Language/Version**: Python 3.x (stdlib subprocess) + Node tooling (npm scripts, wrangler, OpenNext).
**Primary Dependencies**: `wrangler` CLI (`--persist-to`), `@opennextjs/cloudflare` (`preview` passes
args after `--` through to `wrangler dev`). No new dependency.
**Storage**: Cloudflare D1 + R2 local Miniflare state (a directory on disk). Two dirs: `.wrangler/state`
(staging, default) and `.wrangler/state-test` (test).
**Testing**: Existing stdlib `unittest` suites — `scripts/tests/` (pure unit) and
`scripts/integration_tests/` (real-D1). Add a focused unit test for the new `_persist_args` helper.
**Target Platform**: Local dev container + CI (Linux). Local only — no production change.
**Project Type**: Web app (Next.js on Cloudflare Workers) — but this feature touches only
dev-environment tooling (`scripts/`, `package.json`, `.gitignore`, docs).
**Performance Goals**: N/A (a flag append; no hot path).
**Constraints**: With selector unset, behavior MUST be byte-identical to today. `--remote` MUST never
be redirected. Relative selector resolves against repo root.
**Scale/Scope**: ~1 helper + 4 call-site flag appends in `d1.py`, 1 flag forward in `server.py`,
~6 npm-script edits, 1 gitignore check, 2 doc updates, 1 unit test.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- **I. Type Safety & Schema Discipline** — No schema change, no migration, no `auth.schema.ts` touch.
  PASS.
- **II. Cloudflare-Native Architecture** — Keeps the single `DATABASE` binding (NFR-002); no second
  binding, no env-driven binding selection in app code. Isolation is purely a Miniflare persist
  directory, the Cloudflare-sanctioned local-state mechanism. PASS.
- **III. Quality Gates Before Commit** — Will run `pnpm lint` + `pnpm format` (prettier covers
  markdown too — docs are touched). Adds a unit test for the new pure helper; existing suites must
  stay green. PASS.
- **IV. Security & Auth by Default** — No auth/route/secret change. The throwaway better-auth secret
  injection in `server.py` is unchanged. PASS.
- **V. Simplicity & Incremental Delivery** — One env var + one helper, reusing wrangler's built-in
  `--persist-to`. No new abstraction, no new dependency, no app-code change. The env-var seam (vs
  threading an arg through dozens of signatures) is the simplest mechanism that propagates through the
  fan-out + nested subprocesses. PASS.

No violations — Complexity Tracking left empty.

## Project Structure

### Documentation (this feature)

```text
specs/061-isolated-test-db/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/           # Phase 1 output (the selector contract)
└── tasks.md             # Phase 2 output (speckit tasks)
```

### Source Code (repository root)

```text
scripts/
├── common/
│   └── d1.py            # ADD _persist_args(target) helper; append it to the 4 local wrangler
│                        #   shell-outs (execute_sql, query, put_object, get_object)
├── e2e/
│   └── server.py        # FORWARD --persist-to <test dir> to `pnpm preview -- ...` when the
│                        #   selector is set (so the served Worker reads the test DB)
├── tests/
│   └── test_persist_args.py   # NEW unit test for the pure helper (unset/relative/absolute/remote)
└── pipeline-flow.md     # DOC update: two local DBs + selector + *:test scripts

package.json             # ADD db:migrate:test, preview:test, (optional) db:studio:test;
                         #   PREFIX SVHC_WRANGLER_PERSIST on test:py:integration / e2e:seed /
                         #   e2e:smoke / test:e2e. Staging scripts unchanged.
.gitignore               # VERIFY .wrangler covers .wrangler/state-test (add only if needed)
CLAUDE.md                # DOC update: feature-014 section + key-commands
```

**Structure Decision**: Single-repo web app; this feature is confined to dev-environment tooling
(`scripts/`, `package.json`, `.gitignore`, docs). No `src/` files are touched.

## Complexity Tracking

> No constitution violations — not applicable.
