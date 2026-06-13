# Feature Specification: Integration/E2E Smoke Suite — Seeded Local D1/R2 + Browser Flows

**Feature Branch**: `046-e2e-smoke-suite`
**Created**: 2026-06-13
**Status**: Draft
**Input**: User description: "Integration/E2E smoke suite: deterministic local Miniflare D1/R2 seed fixture (synthetic data only), Python integration tests exercising the real atomic-batch writebacks through scripts/common/d1.py against local D1, and a browser E2E smoke against pnpm preview covering sign-in, entries render, alert deep link + analysis dialog, documents statuses, and the auth-gated image route; wired into CI as a separate job"

## Context

The unit suites (TEST-002 Python / TEST-003 TypeScript) cover pure logic but stub the seams where the app actually breaks: the `wrangler`-CLI wrapper executing real SQL batches against D1, the Drizzle queries in API routes, the better-auth middleware gate, R2 image streaming, and the dashboard pages rendering real rows. This feature adds the missing **integration + end-to-end smoke** layer that drives those seams against a real local Miniflare D1/R2 and the real Workers build, using only synthetic data.

This is issue **TEST-004** (depends on **#68**, the TEST-001 CI workflow, which is merged as `.github/workflows/ci.yml`).

## Clarifications

### Session 2026-06-13

Running unattended (one-shot pipeline), so the would-be clarification questions are resolved as recorded design decisions rather than asked interactively. Each is reflected in the Assumptions / Functional Requirements below.

- Q: E2E driver — new `@playwright/test` JS dep, or reuse the Python Playwright already in the toolchain? → A: Reuse Python Playwright `sync_api` (no new JS dependency) — see FR-008 / Assumptions.
- Q: Where do the integration tests live so the fast unit run never needs Miniflare? → A: A separate discovery path (`scripts/integration_tests/`) with its own `pnpm test:py:integration` script; `pnpm test:py` (unit) is unchanged.
- Q: How is the served app reached (origin/port) for the browser smoke? → A: `pnpm preview` (real Workers build via `wrangler dev`) on a fixed local port the harness owns; `BETTER_AUTH_URL`/trusted origins set to match (the existing `.dev.vars` already trusts `:3000`/`:3001`).
- Q: What guarantees the seed is "synthetic only"? → A: A far-future period `2099-01`, placeholder names/`*.svhc.local`/`EXEMPLO` markers and fake CNPJs, derived via `det_id`; no read of any real `data/scrape` artifact (FR-002).
- Q: CI trigger — PR vs nightly? → A: Run on PRs as a separate job if runtime stays ≤ ~10 min; structured so the trigger alone can move it to `main`+nightly later with no test change (FR-010).

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Deterministic synthetic seed of local Miniflare state (Priority: P1)

A maintainer (or CI) runs one command and gets a fresh local Miniflare D1 + R2 populated with a small, fully synthetic fiscal period: a scrape run, an accountability report, reference rows (categories/subcategories/vendors/units), entries, attachments, `attachment_state`, `attachment_analyses` (+ records), documents and `document_entries`, and alerts of several types (including ones whose `metadata` carries deep-link `entry_ids`), plus matching fake page images in the R2 bucket. The seed is idempotent and contains **no real condominium data**.

**Why this priority**: Every other test layer depends on a deterministic, reproducible local state. Without it neither the integration tests nor the browser smoke can run.

**Independent Test**: Run the seed command against a fresh `.wrangler` state; query D1 to confirm the expected row counts per table and confirm the seeded page-image keys exist in R2. Re-running produces the same row set (idempotent).

**Acceptance Scenarios**:

1. **Given** a clean checkout, **When** the seed command runs, **Then** migrations are applied and the synthetic period's rows exist in local D1 with valid foreign keys and the page images exist in the local R2 bucket.
2. **Given** an already-seeded state, **When** the seed command runs again, **Then** it completes without error and the row set is unchanged (deterministic ids; no duplicate rows).
3. **Given** the seeded data, **When** inspected, **Then** it is recognizably synthetic (placeholder vendor names, fake CNPJs, `*.svhc.local` / "EXEMPLO" markers) — no real names, CNPJs, or amounts from any real ledger.

---

### User Story 2 - Python integration tests over the real atomic-batch writebacks (Priority: P1)

A maintainer runs the integration test suite, which exercises the real `scripts/common/d1.py` `execute_sql`/`query`/`upsert_*` path and the analysis writebacks against the seeded local D1 — validating the SQL the unit tests only string-assert actually behaves atomically and idempotently against SQLite.

**Why this priority**: The atomic delete-then-insert writebacks (features 024/025/026/028/035) are the highest-risk seam — a partial-commit bug there silently corrupts derived data. These tests are the only place the real SQL runs.

**Independent Test**: With the seed applied, run the integration tests; each asserts the post-state of D1 via `d1.query` after invoking the real writeback function (or its CLI), and re-running is idempotent.

**Acceptance Scenarios**:

1. **Given** a seeded pending attachment, **When** the rolled-up `attachment_analyses` writeback runs (`_merge_and_write`), **Then** in one batch the old analysis rows are cleared, the new roll-up + records are inserted, `attachment_state.classified_at` is stamped, and the attachment's `page_classifications` staging rows are deleted.
2. **Given** a classified attachment, **When** `mark-pending` runs for it, **Then** `attachment_state.classified_at` is cleared to NULL and its staging rows are deleted in one batch.
3. **Given** seeded `attachment_analyses` carrying a document number + 14-digit CNPJ, **When** `build-documents` runs twice, **Then** the first run upserts the `documents` + `document_entries`, and a second run after an analysis key change prunes the now-stale rows (no zombie document/link survives).
4. **Given** a seeded period, **When** the feature-028 reconciliation SQL batch (built by the pure `build_reconciliation`) is executed against D1 for a scraped set missing one entry, **Then** the vanished entry and its analysis-owned dependents are cascade-deleted and a `portal_row_vanished` alert is written — all in one batch.
5. **Given** any of the above writebacks, **When** it is invoked a second time with the same input, **Then** the resulting D1 state is identical (idempotent).

---

### User Story 3 - Browser E2E smoke over the running app (Priority: P2)

A maintainer (or CI) builds and serves the real Workers app (`pnpm preview`) against the seeded local state and runs a headless browser that walks the core user surfaces once each, plus the auth gate.

**Why this priority**: This is the only layer that exercises the full stack — middleware gate, Drizzle queries in API routes, R2 streaming, and React rendering — end to end. It is P2 (behind seed + integration) because it is slower and needs the build.

**Independent Test**: Start `pnpm preview` against the seed, run the browser smoke; each surface check passes against the seeded synthetic data and the auth-gated image route returns bytes when authenticated and 401/403 when not.

**Acceptance Scenarios**:

1. **Given** the seeded app and a synthetic admin user, **When** the browser signs in, **Then** it lands on `/dashboard` (and an unauthenticated visit to `/dashboard/*` redirects to the sign-in surface).
2. **Given** signed in, **When** the entries page opens for the seeded period, **Then** the seeded entries render.
3. **Given** an alert with a deep-link `entry_id`, **When** the alert's deep link is followed, **Then** the entries page selects the period, highlights the row, and auto-opens the analysis dialog; **and** a deep link to a non-existent entry shows the feature-037 not-found notice without an error.
4. **Given** signed in, **When** the documents page opens, **Then** the seeded documents render with their over/within status badges.
5. **Given** the seeded page-image key, **When** the auth-gated image route is requested with a valid session, **Then** it streams the image bytes; **When** requested with no session, **Then** it returns an unauthorized status (no bytes).

---

### User Story 4 - Wired into CI as a separate job (Priority: P2)

The suite runs in CI as a job distinct from the existing fast `verify` job, so the slower build + Miniflare path does not block the quick quality gates and its failures are independently visible.

**Why this priority**: Required by the issue, but the suite has value locally even before CI wiring; hence P2.

**Independent Test**: Open a PR; observe a second CI job (e.g. `e2e`) that seeds, runs the Python integration tests, and runs the browser smoke, reporting pass/fail separately from `verify`.

**Acceptance Scenarios**:

1. **Given** a pull request, **When** CI runs, **Then** the integration/E2E job runs in parallel with `verify` and its result is reported separately.
2. **Given** the integration/E2E job, **When** it runs, **Then** it provisions a fresh local Miniflare state, applies migrations, seeds synthetic data, runs the Python integration tests, builds + serves the app, and runs the browser smoke — failing the job if any step fails.

### Edge Cases

- **Stale local state**: the seed must apply migrations and converge regardless of any prior `.wrangler` content (or the harness starts from a clean state directory).
- **Port already in use**: the browser smoke must target a known port for `pnpm preview`; if the chosen port is occupied the harness fails fast with a clear message rather than hanging.
- **Trusted origin mismatch**: better-auth rejects sign-in if the request Origin is not trusted; the harness must serve with the browser's origin trusted (already present in `.dev.vars`).
- **Browser binary missing in CI**: the CI job must install the browser the driver needs before the smoke runs.
- **No real data leakage**: a guard (review + naming convention) ensures the seed module never imports or reads any real `data/scrape` artifact.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The suite MUST provide a single deterministic seed entry point that applies all D1 migrations to the local Miniflare state, inserts a synthetic fiscal period across all tables needed by the tested surfaces, and uploads matching synthetic page images to the local R2 bucket.
- **FR-002**: All seeded data MUST be synthetic — no real condominium names, CNPJs, amounts, or scraped artifacts may appear in the repo. Deterministic ids MUST be derived the same way the pipeline derives them (`det_id`) so the seed matches what production code would produce.
- **FR-003**: The seed MUST be idempotent: re-running yields the same row set (no duplicates), enabling repeated test runs.
- **FR-004**: The Python integration tests MUST exercise the real `scripts/common/d1.py` execution path (`execute_sql`/`query`/`upsert_*`) against the seeded local D1 — not stubbed seams — and MUST be separated from the unit suite so the fast unit run never requires Miniflare/`wrangler`.
- **FR-005**: The integration tests MUST cover at minimum: the `_merge_and_write` atomic roll-up+stamp+prune batch; `mark-pending` clear+invalidate; `build-documents` upsert-then-prune across two runs; and the feature-028 reconciliation cascade SQL — each asserted by reading back D1 state and each verified idempotent.
- **FR-006**: The browser E2E smoke MUST cover, once each (happy path + the auth gate, not exhaustive matrices): sign-in landing on the dashboard and the unauthenticated redirect; the entries page rendering the seeded period; the alert deep link selecting/highlighting the row and auto-opening the analysis dialog; the feature-037 not-found notice on a dead deep link; the documents page rendering seeded over/within statuses; and the auth-gated image route streaming bytes when authenticated and returning an unauthorized status when not.
- **FR-007**: The browser smoke MUST run against the real Workers build served by `pnpm preview` (not `next dev`), with a synthetic admin user provisioned (sign-up + role elevation) so the auth-gated surfaces are reachable.
- **FR-008**: The E2E driver MUST be chosen to avoid a new JavaScript dependency where the existing toolchain suffices. (Decision recorded in Assumptions: Python Playwright `sync_api`, already in the scraper toolchain — no `@playwright/test` JS dependency added.)
- **FR-009**: The suite MUST be runnable locally via a documented command (added to `package.json` scripts) and wired into CI as a job separate from the existing `verify` job, provisioning the build + Miniflare itself and reporting pass/fail independently.
- **FR-010**: The CI job MUST run on pull requests if its total runtime stays reasonable (target ≤ ~10 min). The harness MUST be structured so that, if runtime later proves too high, the job can be moved to `main` pushes + a nightly schedule by changing only the workflow trigger — no test code change.
- **FR-011**: The suite MUST NOT scrape the real brcondos portal nor require any production secret or `--remote` access; it operates entirely against local Miniflare.
- **FR-012**: Failures MUST be diagnosable: the seed and each test surface MUST emit a clear message on failure (which surface, expected vs actual), and the harness MUST not hang indefinitely (bounded waits/timeouts).

### Key Entities *(include if feature involves data)*

- **Synthetic seed dataset**: one fiscal period (`2099-01`, a far-future marker to avoid colliding with any real period) comprising a scrape run, accountability report, reference rows, a handful of entries (some sharing an NF), their attachments + `attachment_state` (mix of pending and classified), `attachment_analyses` (+ records), documents + `document_entries` (one over-claim to exercise the "over" badge, one within), and alerts (at least one `attachment_amount_mismatch` with a deep-link `entry_id`, one `document_overpayment` spanning multiple entries).
- **Synthetic admin user**: a better-auth `users` row (email `e2e@svhc.local`) with `role='admin'`, created via sign-up then elevated, used by the browser smoke to reach auth-gated surfaces.
- **Synthetic page images**: small fake PNGs uploaded to R2 under the seeded attachments' `file_path`-derived keys, so the image route has bytes to stream.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A maintainer can provision the full local test state (D1 + R2) with one command in under 2 minutes on a clean checkout.
- **SC-002**: The Python integration suite runs to green against the seeded local D1, covering at least the four named writebacks, each asserted idempotent.
- **SC-003**: The browser smoke completes all six surface checks (5 happy paths + 1 auth gate) against the served app with zero manual steps.
- **SC-004**: CI shows a second job distinct from `verify` whose pass/fail reflects the seed + integration + browser smoke, and the existing fast `verify` job is unaffected (same runtime, no new required setup).
- **SC-005**: A reviewer can confirm by inspection that the seed contains only synthetic data (no real condominium identifiers).
- **SC-006**: The fast unit suites (`pnpm test:py` / `pnpm test:ts`) continue to pass and require no Miniflare/`wrangler`/browser — the integration/E2E layer is additive and isolated.

## Assumptions

- **E2E driver = Python Playwright `sync_api`.** It is already installed in the scraper toolchain (`scripts/` via `uv`) with a Chromium binary present, so the smoke reuses it with **no new JS dependency** (`@playwright/test` is deliberately not added). The smoke lives under `scripts/` alongside the other Python tests and is invoked through `uv run`. This satisfies FR-008.
- **Seed lives in Python under `scripts/`** (e.g. `scripts/e2e/seed.py`), reusing `scripts/common/d1.py` (`upsert_tables`/`execute_sql`/`put_object`), `det_id`, and `now_ms` so seeded rows are byte-identical to what the pipeline writes. Migrations are applied via `wrangler d1 migrations apply DATABASE --local`.
- **Integration tests are separated by discovery path** (e.g. `scripts/integration_tests/`, run via a dedicated `pnpm test:py:integration` script), so `pnpm test:py` (unit, discover `-s tests`) never touches Miniflare. CI runs them in the separate job.
- **The served app**: `pnpm preview` builds with OpenNext and serves via `wrangler dev` against local Miniflare on a chosen port. The harness sets `BETTER_AUTH_URL`/trusted origins to match the port (the existing `.dev.vars` already trusts `:3000`/`:3001`); the browser navigates that origin. The harness starts the server, waits for readiness, runs the smoke, and tears it down.
- **Synthetic period id** is a far-future `2099-01` to guarantee no overlap with any real scraped period, making the seed safe to apply to a developer's local state.
- **The auth-gated image route returns 403 for an authenticated non-privileged role and a redirect/401 for no session.** The smoke asserts the unauthenticated case returns a non-2xx (no image bytes); the precise code (401 vs 307 redirect to sign-in) is asserted loosely as "not a streamed image".
- **CI browser install**: the E2E job runs Python Playwright's `playwright install --with-deps chromium` before the smoke; the unit jobs do not.
- **I18N caveat (from the issue)**: UI assertions target stable, language-independent anchors (element roles / seeded values / URL params) rather than pt-BR copy where possible, so they survive the I18N work; where a label must be asserted, the pt-BR catalog label is used.
- **No D1 schema change, no migration, no mirror-table write at runtime by the tests beyond the seed's synthetic inserts.** The seed writes mirror tables because it stands in for the scraper in a local-only context; it never touches remote.
