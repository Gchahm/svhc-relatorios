# Tasks: Isolated local test database (separate from the human's staging DB)

**Feature**: `061-isolated-test-db` | **Spec**: [spec.md](./spec.md) | **Plan**: [plan.md](./plan.md)

This feature is dev-environment infra only: no `src/`, no schema, no migration. The "foundational"
work is the persist-selector seam in `scripts/common/d1.py`; the user stories layer the entrypoints
and human-facing scripts on top.

## Phase 1: Setup

- [x] T001 Verify `.gitignore` already ignores `.wrangler` (covers `.wrangler/state-test`); add an
      explicit rule only if missing — in `/home/agent/workspace/svhc-relatorios/.gitignore` (FR-011).

## Phase 2: Foundational (blocks all user stories)

- [x] T002 Add a pure helper `_persist_args(target: Target) -> list[str]` to
      `/home/agent/workspace/svhc-relatorios/scripts/common/d1.py`: returns `[]` for `target != "local"`
      OR when `SVHC_WRANGLER_PERSIST` is unset/empty; otherwise returns `["--persist-to", <dir>]` with a
      relative value resolved against `_REPO_ROOT` and an absolute value used as-is. Read the env var via
      `os.environ` (add `import os`). (FR-001, FR-003, FR-004)
- [x] T003 Append `*_persist_args(target)` to the four local wrangler argv builders in
      `/home/agent/workspace/svhc-relatorios/scripts/common/d1.py` — `execute_sql`, `query`,
      `put_object`, `get_object` — after the existing flags (before/with `target_flag(target)`), so the
      flag is present for local and absent for remote. (FR-002, FR-005)
- [x] T004 [P] Add unit test `/home/agent/workspace/svhc-relatorios/scripts/tests/test_persist_args.py`
      covering: unset ⇒ `[]`; empty string ⇒ `[]`; relative ⇒ resolves against repo root (absolute,
      ends with the relative path); absolute ⇒ unchanged; `target="remote"` with the var set ⇒ `[]`.
      Use `unittest` + `unittest.mock.patch.dict(os.environ, ...)` (no D1/network). Run via
      `cd scripts && uv run python -m unittest discover -s tests -t .`.

**Checkpoint**: `d1.py` honors the selector for local, ignores it for remote, and the unit suite is
green. Everything below depends on this.

## Phase 3: User Story 1 — Agent test suite isolates from staging (P1)

**Goal**: The test/seed/e2e suites read/write only `.wrangler/state-test`; staging is untouched.

**Independent test**: Seed test DB, write a sentinel into staging (`.wrangler/state`), run the suite,
confirm the staging sentinel survives (quickstart "Verify isolation").

- [x] T005 [US1] Prefix `SVHC_WRANGLER_PERSIST=.wrangler/state-test` on the four test entrypoints in
      `/home/agent/workspace/svhc-relatorios/package.json`: `test:py:integration`, `e2e:seed`,
      `e2e:smoke`, `test:e2e`. Use `cross-env`-free `VAR=val cmd` form consistent with the existing
      `db:studio:prod` script (`NODE_ENV=production drizzle-kit studio`). Staging scripts unchanged.
      (FR-006, FR-010)
- [x] T006 [US1] Verify the integration harness + `scripts/e2e/seed.py` need NO logic change — they
      inherit the exported var through the in-process `d1.py` calls. (Read-only check; confirm in
      `scripts/integration_tests/_harness.py` and `scripts/e2e/seed.py`.)

**Checkpoint**: `pnpm e2e:seed` + `pnpm test:py:integration` write only the test dir.

## Phase 4: User Story 3 — Browser smoke serves against the test DB (P1)

**Goal**: The preview server the smoke launches serves the test DB so the smoke sees seeded data.

**Independent test**: `pnpm test:e2e` builds, serves against `.wrangler/state-test`, and the smoke's
surface checks pass against the seeded synthetic `2099-01` data.

- [x] T007 [US3] In `/home/agent/workspace/svhc-relatorios/scripts/e2e/server.py`, when
      `SVHC_WRANGLER_PERSIST` is set, append `--persist-to <resolved dir>` to the
      `["pnpm", "preview", "--", "--port", str(port)]` argv (resolve relative against `_REPO_ROOT`,
      mirroring `d1.py`). When unset, the argv is unchanged (staging). (FR-007)

**Checkpoint**: `pnpm test:e2e` serves and smokes the test DB end-to-end.

## Phase 5: User Story 2 — Human-facing `*:test` scripts (P2)

**Goal**: Discoverable scripts to bootstrap/eyeball the test DB; staging scripts untouched.

**Independent test**: `pnpm db:migrate:test` creates a migrated `.wrangler/state-test`; `pnpm
preview:test` serves the seeded test DB.

- [x] T008 [US2] Add `db:migrate:test` to `/home/agent/workspace/svhc-relatorios/package.json`:
      `wrangler d1 migrations apply DATABASE --local --persist-to .wrangler/state-test`. (FR-008)
- [x] T009 [US2] Add `preview:test` to `/home/agent/workspace/svhc-relatorios/package.json`:
      `opennextjs-cloudflare build && opennextjs-cloudflare preview -- --persist-to .wrangler/state-test`.
      (FR-009)

## Phase 6: Polish & Docs (cross-cutting)

- [x] T010 [P] Update `/home/agent/workspace/svhc-relatorios/scripts/pipeline-flow.md`: replace the
      "default is local Miniflare `.wrangler/state`" note with the two-local-DBs model, the
      `SVHC_WRANGLER_PERSIST` selector, and the `*:test` scripts (incl. self-bootstrap + `db:migrate:test`).
      (FR-012)
- [x] T011 [P] Update `/home/agent/workspace/svhc-relatorios/CLAUDE.md`: in the key-commands block add
      the `*:test` scripts; in the "Direct-to-D1 scrape & analysis (feature 014)" pattern add a sentence
      on the two local DBs + the `SVHC_WRANGLER_PERSIST` selector (default = staging; tests isolate).
      (FR-012)
- [x] T012 Run `pnpm lint` and `pnpm format` (prettier covers markdown — docs are touched);
      run `cd scripts && uv run python -m unittest discover -s tests -t .` (pure unit suite stays green).
- [x] T013 Verify acceptance manually per quickstart: sentinel-in-staging survives the suite (SC-003);
      `db:migrate:test` builds an independent test DB (SC-002); selector-unset behavior unchanged
      (SC-001); `--remote` never gets the flag (SC-005); `.wrangler/state-test` gitignored (SC-006).

## Dependencies

- Phase 1 (T001) — independent.
- Phase 2 (T002→T003, T004) — foundational; blocks Phases 3-5. T004 [P] can run alongside T003 once
  T002 exists.
- Phase 3 (US1), Phase 4 (US3), Phase 5 (US2) — each depends only on Phase 2; mutually independent
  (different scripts/files), so parallelizable after Phase 2.
- Phase 6 — docs (T010, T011 [P]) any time after the design is fixed; T012/T013 last.

## Parallel opportunities

- T004 (unit test) ‖ T003 once T002 lands.
- T005 (US1), T007 (US3), T008+T009 (US2) edit `package.json`/`server.py` — `package.json` edits
  (T005, T008, T009) touch the same file so serialize those; T007 (server.py) is independent.
- T010 ‖ T011 (different docs).

## MVP scope

Phase 2 + Phase 3 (US1) = the core isolation guarantee (agents can't clobber staging via the suite).
US3 and US2 complete the smoke and human ergonomics.
