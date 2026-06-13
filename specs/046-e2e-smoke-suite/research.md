# Phase 0 Research: Integration/E2E Smoke Suite

All spec-level unknowns were resolved during specify/clarify. This records the decisions, their rationale, and the rejected alternatives.

## D1: E2E browser driver

- **Decision**: Python Playwright (`playwright.sync_api`), driven from `scripts/e2e/smoke.py` via `uv run`.
- **Rationale**: `playwright` is already a scraper dependency (`scripts/pyproject.toml`) with a Chromium binary installed at `/opt/playwright/...` (verified: `sync_playwright().chromium.executable_path` resolves). Reusing it adds **zero** new dependency and keeps the whole test layer in one language/toolchain. Constitution Principle V (Simplicity) favors this.
- **Alternatives considered**:
  - `@playwright/test` (JS) — first-class test runner, fixtures, trace viewer. **Rejected**: a new top-level npm dependency + a new test config + a second browser install in CI, all to duplicate capability the Python toolchain already has. The issue explicitly asked this to be justified; it isn't justified for a 6-check smoke.
  - Drive via the existing Playwright **MCP browser** (as `ui-login`/`verify` skills do) — **Rejected**: the MCP browser is an interactive agent tool, not a headless CI-runnable test harness.
  - `curl`-only smoke (no browser) — **Rejected**: cannot exercise the client-side deep-link highlight + dialog auto-open (feature 018/037), which is a named requirement (FR-006).

## D2: Test isolation (unit vs integration)

- **Decision**: Integration tests live in a **separate discovery path** `scripts/integration_tests/` with their own `pnpm test:py:integration` script; the existing `pnpm test:py` (`discover -s tests -t .`) is unchanged and never touches Miniflare/`wrangler`.
- **Rationale**: SC-006 requires the fast unit suite to stay Miniflare-free. Separate discovery roots is the simplest isolation (no marker plumbing in stdlib `unittest`, which the repo standardizes on — no pytest).
- **Alternatives considered**: `unittest` skip-decorators gated on an env var inside `scripts/tests/` — **Rejected**: pollutes the unit suite with conditional D1 setup and risks accidental Miniflare reads in the fast job.

## D3: Driving the real writebacks

- **Decision**: Import and call the **real** functions against seeded local D1: `attachments._merge_and_write(result, target="local")`, `extractions.mark_pending(...)`, the `build-documents` CLI (`python -m analysis build-documents`), and `reconcile.build_reconciliation(...)` → `d1.execute_sql(result.sql, target="local")`. Assert post-state with `d1.query(...)`.
- **Rationale**: FR-004/FR-005 require the *real* `scripts/common/d1.py` execution path, not stubs. These functions take plain inputs (`AttachmentAnalysisResult` is a dataclass; `build_reconciliation` is pure and returns SQL), so the tests construct minimal synthetic inputs and run the actual SQL batch against SQLite — exactly what production does locally.
- **Note**: `runner.py`'s `_reconcile_period`/`_scrape_periodo` import `playwright` and read live D1; the **pure** `build_reconciliation` is importable without playwright (stdlib-only, per CLAUDE.md). The test uses the pure builder + the real `execute_sql`, which is the same SQL the runner would submit.
- **Alternatives considered**: shelling out to every writeback via its CLI — **Rejected** for `_merge_and_write` (no standalone CLI; it runs inside `apply-extractions` which needs `page_classifications` staging + image grouping). Direct call is closer to the unit-tested seam and avoids fragile orchestration. `build-documents` *does* have a clean global CLI, so that one uses the CLI.

## D4: Synthetic-data guarantee

- **Decision**: Period `2099-01`; vendor/issuer names use `EXEMPLO`/placeholder strings; CNPJs are obviously fake but 14-digit-valid (e.g. `11222333000181`); emails `*@svhc.local`. All ids derived via `det_id(...)` exactly as the pipeline does. The seed module reads **no** `data/scrape` artifact.
- **Rationale**: FR-002/SC-005. A far-future period guarantees no collision with a real scrape; the markers make synthetic origin obvious on inspection.

## D5: Serving the app for the smoke

- **Decision**: `scripts/e2e/server.py` runs `pnpm preview` (OpenNext build → `wrangler dev` on local Miniflare) on a fixed port, polls readiness (`GET /` returns 200/307) with a bounded timeout, runs the smoke, then terminates the process group. The synthetic admin is provisioned via `POST /api/auth/sign-up/email` then `UPDATE users SET role='admin'` through `wrangler d1 execute --local` (the `ui-login` mechanism). `.dev.vars` already trusts `localhost:3000`/`:3001`.
- **Rationale**: FR-007 requires the *real Workers build*, not `next dev`. The `ui-login` skill documents the exact origin/role gotchas; the harness encodes them so it runs unattended.
- **Alternatives considered**: `next dev` — **Rejected** by FR-007 (it doesn't exercise the OpenNext/Workers path the integration layer is meant to cover).

## D6: CI trigger

- **Decision**: A second job `e2e` in `.github/workflows/ci.yml`, running on the same `pull_request` + `push: main` triggers as `verify`, but as an independent job (its own runner, own steps). It installs Python Chromium (`playwright install --with-deps chromium`), applies migrations, seeds, runs `test:py:integration`, builds + serves, runs the smoke.
- **Rationale**: FR-009/FR-010. Keeping it on PRs gives the fastest feedback; it is structured so that if runtime later exceeds budget, only the job's `on`/`if` needs to change (move to `push: main` + `schedule`) — no test-code change.
- **Alternatives considered**: nightly-only from the start — **Rejected**: the issue prefers PR-gating "if runtime stays reasonable"; a 6-check smoke + 4 integration tests + one build is expected to fit ≤ ~10 min.
