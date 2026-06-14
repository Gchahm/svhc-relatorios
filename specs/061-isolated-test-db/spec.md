# Feature Specification: Isolated local test database (separate from the human's staging DB)

**Feature Branch**: `061-isolated-test-db`
**Created**: 2026-06-14
**Status**: Draft
**Input**: GitHub issue #107 (DX-001)

## Problem

Every local command shares **one** Miniflare state directory (`.wrangler/state`). The Python
wrangler wrapper and the npm scripts (`db:migrate:dev`, `preview`, `db:studio:dev`) all read/write
that same on-disk database. As a result, the agents' automated test/seed/e2e tooling and the human's
manual testing collide on a single local database: the seed upserts a synthetic period and fake
images, the integration harness DELETEs the synthetic period's analysis-owned rows between tests, and
the e2e/integration suites drive real writebacks against that DB. Any of those an agent runs can
clobber data the human is working with.

We want two **isolated local databases**:

- a **test DB** the agents + automated test/seed/e2e suites use (wipe-and-reseed freely), and
- a **staging DB** the human uses for manual testing (agents never touch it via the test suites).

This affects **local only** — production (`--remote`) is untouched.

## User Scenarios & Testing

### User Story 1 — Agent runs the test suite without clobbering staging (Priority: P1)

An agent runs the automated test/seed/e2e suites. Those write only to the isolated test database; the
human's staging database is left exactly as it was — no deletes, no reseed.

**Why this priority**: This is the core value of the feature — protecting the human's manual-testing
data from automated test tooling.

**Acceptance**:

1. **Given** distinct sentinel rows exist in the staging DB and the test DB has been seeded, **When**
   the full agent test suite (seed + integration + e2e) runs, **Then** the staging sentinel rows are
   untouched (no deletes, no reseed).
2. **Given** `SVHC_WRANGLER_PERSIST` is unset, **When** any local command runs, **Then** it behaves
   exactly as today (state in `.wrangler/state` = staging) — no regression.

### User Story 2 — Human keeps their habits; opts into the test DB only when wanted (Priority: P2)

The human continues using their existing commands (`dev`, `preview`, `db:migrate:dev`,
`db:studio:dev`) against staging with no change. New, explicit `*:test` scripts let them bootstrap,
migrate, and eyeball the isolated test DB on demand.

**Acceptance**:

1. **Given** a clean checkout, **When** the human runs `pnpm db:migrate:test`, **Then** an
   independent migrated database is created under the test state directory, leaving the staging DB
   untouched.
2. **Given** the test DB is seeded, **When** the human runs `pnpm preview:test`, **Then** the served
   app reads the seeded synthetic test data (not staging).

### User Story 3 — Browser smoke serves against the test DB (Priority: P1)

The browser smoke serves the real Workers build against the test database, so it sees the seeded
synthetic data rather than an empty or staging database.

**Acceptance**:

1. **Given** the test DB has been seeded with the synthetic `2099-01` period, **When** the browser
   smoke (`pnpm test:e2e`) runs (build + serve + teardown), **Then** the served app sees the seeded
   synthetic data, proving the preview server honors the test persist directory.

### Edge Cases

- A `--remote` (production) invocation must **never** receive the test-DB redirection.
- Relative persist-dir values must resolve against the repo root regardless of the process CWD (the
  wrapper runs wrangler with `cwd = repo root`, while npm scripts run from `scripts/`).
- A single high-level call (e.g. a full analysis run) fans out to dozens of wrangler shell-outs and
  nested subprocesses; the redirection must propagate to all of them without threading an argument
  through every signature.

## Requirements

### Functional Requirements

- **FR-001**: The system MUST support an internal selector (an environment variable,
  `SVHC_WRANGLER_PERSIST`) that names a Miniflare persist directory co-locating that invocation's
  local D1 + R2 + KV state.
- **FR-002**: When a local (non-remote) wrangler invocation runs and the selector is set, the system
  MUST direct that invocation's state to the selected directory; when the selector is unset, the
  invocation MUST use wrangler's default state directory (the staging DB) — preserving today's
  behavior exactly.
- **FR-003**: A `--remote` (production) invocation MUST NEVER be redirected by the selector.
- **FR-004**: A relative selector value MUST resolve against the repo root.
- **FR-005**: The selector MUST apply to every local wrangler shell-out the Python wrapper performs
  (SQL execute, query, R2 put, R2 get).
- **FR-006**: The test/seed/e2e entrypoints (`test:py:integration`, `e2e:seed`, `e2e:smoke`,
  `test:e2e`) MUST set the selector to the test state directory so their processes (and the nested
  wrapper calls they make) read/write only the test DB.
- **FR-007**: The browser smoke's served app MUST be served against the same test state directory so
  it reads the seeded synthetic data.
- **FR-008**: The system MUST provide a `db:migrate:test` script that creates/migrates the
  independent test DB under the test state directory.
- **FR-009**: The system MUST provide a `preview:test` script that serves the app against the test DB.
- **FR-010**: The existing staging scripts (`dev`, `preview`, `db:migrate:dev`, `db:studio:dev`) MUST
  remain unchanged and continue to target the default (staging) state.
- **FR-011**: The test state directory MUST be gitignored.
- **FR-012**: Documentation (the pipeline-flow doc and CLAUDE.md) MUST describe the two local DBs, the
  selector env var, and the `*:test` scripts, including that the test suites self-bootstrap the test
  DB and that `db:migrate:test` performs an explicit migrate.

### Non-Functional / Constraints

- **NFR-001**: No D1 schema change, no migration, no app-code (`src/`) change — dev-environment infra
  only.
- **NFR-002**: No second D1 binding / second `database_name` in `wrangler.toml`. Isolation is by
  persist directory; the app keeps one `DATABASE` binding.
- **NFR-003**: CI's e2e job MUST stay green (its test scripts carry the selector; the ephemeral runner
  behaves equivalently).

## Key Entities

- **Test DB state directory**: an isolated Miniflare persist directory holding the test DB's D1 + R2 +
  KV state, used by the automated test/seed/e2e suites.
- **Staging DB state directory**: wrangler's default Miniflare persist directory, used by all
  non-test local commands (the human's manual testing).
- **Persist selector**: an environment variable naming the persist directory for the current local
  invocation; unset means the staging default.

## Success Criteria

- **SC-001**: With the selector unset, all local commands behave exactly as today (no regression).
- **SC-002**: `db:migrate:test` creates/migrates an independent test DB under the test state dir,
  leaving the staging DB untouched.
- **SC-003**: Running the agent test suite (seed + integration + e2e) leaves staging sentinel rows
  untouched — no deletes, no reseed.
- **SC-004**: The browser smoke serves against the test DB and sees the seeded synthetic `2099-01`
  data.
- **SC-005**: `--remote` / production paths are unchanged (no redirection ever applied for remote).
- **SC-006**: The test state directory is gitignored.

## Assumptions

- **A-001**: The selector env var is named `SVHC_WRANGLER_PERSIST` and the test state dir is
  `.wrangler/state-test` (both per the issue's stated decisions).
- **A-002**: `.wrangler` is already gitignored, which covers `.wrangler/state-test` — verify and add
  an explicit rule only if needed.
- **A-003**: `pnpm preview` (OpenNext) forwards flags after `--` through to the underlying
  `wrangler dev`, so the preview can be pointed at the test persist dir; the exact pass-through form
  is confirmed during planning/implementation.
- **A-004**: The default routing is intentionally "tests isolate; everything else = staging." An
  agent told to run the real pipeline locally outside the test entrypoints still hits staging unless
  it sets the selector itself. This is an accepted, documented boundary (a non-goal to auto-isolate).
- **A-005**: `db:studio:test` (Drizzle Studio against the test DB) is an optional nice-to-have; it is
  included only if low-cost, otherwise deferred without affecting acceptance.

## Non-Goals

- No second D1 binding / second `database_name` in `wrangler.toml`.
- Not changing the default so agents' non-test manual pipeline runs auto-isolate (accepted boundary,
  A-004).
- No production/remote isolation work.

## Dependencies

- None. Independent of the open EXTRACT/TRIAGE issues (per the issue).
