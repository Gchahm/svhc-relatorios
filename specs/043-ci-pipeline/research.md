# Phase 0 Research: CI pipeline

All Technical Context items were resolvable from the repo + issue; no NEEDS CLARIFICATION remained.
Decisions below are the resolved unknowns.

## D1: Build gate — `next build` vs `tsc --noEmit`

- **Decision**: Run `tsc --noEmit` via a new `typecheck` script as the build/type gate.
- **Rationale**: The issue explicitly allows it ("alternatively add `tsc --noEmit` as a faster
  `typecheck` script and run that"). `next build` would require OpenNext/Cloudflare context and is much
  slower; `tsc --noEmit` catches the type errors the issue cares about (its stated reason for a build
  step). Verified locally: `tsc --noEmit` exits 0 cleanly. The existing `build` script is untouched.
- **Alternatives considered**: `next build` (slower, needs CF context), `next build` with stubbed env
  (extra complexity, violates Simplicity). Rejected.

## D2: Toolchain versions / pinning

- **Decision**: Node 22; pnpm via `pnpm/action-setup@v4` (version 11, matching the dev container);
  `uv` via `astral-sh/setup-uv@v5` with Python 3.12.
- **Rationale**: Dev container runs Node 22, pnpm 11.5.3, uv 0.11.20; `scripts/pyproject.toml` requires
  Python `>=3.12`; lockfile is pnpm `lockfileVersion: '9.0'`. `package.json` has no `packageManager`
  field and there is no `.nvmrc`, so we pin in the workflow directly. We do **not** add a
  `packageManager` field (out of scope; avoids touching install behavior for contributors).
- **Alternatives considered**: Reading pnpm version from a `packageManager` field (absent), or a
  matrix across Node versions (issue forbids a matrix). Rejected.

## D3: Dependency caching (both ecosystems)

- **Decision**: Cache the pnpm store via `actions/setup-node@v4` `cache: pnpm` (keyed on
  `pnpm-lock.yaml`); enable `uv` caching via `setup-uv`'s `enable-cache: true` (keyed on
  `scripts/uv.lock`).
- **Rationale**: Both are first-party cache mechanisms — no hand-rolled `actions/cache` keys needed,
  satisfying FR-005 with minimal surface. `setup-node`'s pnpm cache requires pnpm to be installed
  first, so `pnpm/action-setup` runs before `setup-node`.
- **Alternatives considered**: Manual `actions/cache` blocks (more YAML, more drift). Rejected.

## D4: Python step hermeticity

- **Decision**: Run the Python suite with `uv run python -m unittest discover -s tests -t .` from
  `scripts/` (exactly the existing `test:py` script), and do **not** install Playwright browsers.
- **Rationale**: Verified the `scripts/tests/` modules import only the stdlib + the project's pure
  helper modules; the three files mentioning playwright/wrangler/dotenv do so in comments/strings only
  (`grep` of import lines returns nothing for those packages). `uv run` resolves the project venv;
  importing the test modules never triggers a playwright/dotenv import, so no browser download or
  network is required. FR-006 is satisfied without changing any test.
- **Alternatives considered**: Stripping playwright from `pyproject.toml` (would break the scraper),
  or a separate test-only dependency group (unnecessary — tests don't import the deps). Rejected.

## D5: Triggers, permissions, concurrency

- **Decision**: `on: pull_request` + `on: push: branches: [main]`. Top-level
  `permissions: contents: read`. A `concurrency` group `${{ github.workflow }}-${{ github.ref }}` with
  `cancel-in-progress: true`.
- **Rationale**: Matches FR-001; least-privilege permissions (verification only, no writes/deploy,
  FR-009 + Principle IV); concurrency cancels superseded runs (A-07, edge case "concurrent pushes").
- **Alternatives considered**: Default (write) permissions — rejected as needlessly broad.

## D6: Pre-existing repo cleanliness (FR-008)

- **Decision**: Add a trailing newline to `CLAUDE.md` (the sole tracked file failing
  `prettier --check`); add `.next.broken.*` to `.prettierignore` and `.gitignore`.
- **Rationale**: Verified `prettier --check .` flags only `CLAUDE.md` among tracked files (the rest of
  the 299 warnings were the untracked `.next.broken.1781301815/` stray build dir, which a fresh CI
  checkout never contains). Ignoring the stray pattern keeps local `format:check` clean and prevents a
  future failed build from polluting the gate. `pnpm lint`, `test:ts`, `test:py`, and `tsc --noEmit`
  already pass locally with exit 0.
- **Alternatives considered**: `prettier --write` across the repo (would churn 299 files including the
  stray dir; violates "minimal"). Rejected — only the one real violation is fixed.
