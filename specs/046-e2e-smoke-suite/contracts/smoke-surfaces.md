# Contract: Browser E2E Smoke Surfaces (`scripts/e2e/smoke.py`)

Driver: Python Playwright `sync_api`, headless Chromium. Origin: the `pnpm preview` server started by `scripts/e2e/server.py` (fixed port, e.g. `http://localhost:3000`). One happy path + the auth gate per surface (smoke, not a matrix). Every check has a stable, language-independent anchor where possible (URL params, element roles, seeded values, HTTP status) so it survives the I18N work.

| # | Surface | Action | Pass anchor |
|---|---------|--------|-------------|
| S1a | Auth gate (negative) | navigate `/dashboard` with **no** session | redirected to a sign-in surface (URL is `/` or `/sign-in`, not `/dashboard`) |
| S1b | Sign-in (positive) | fill email `e2e@svhc.local` + password, submit | URL becomes `/dashboard` |
| S2 | Entries render | navigate `/dashboard/entries?period=2099-01` | a seeded entry value renders (e.g. row containing the E3 amount / description text) |
| S3 | Alert deep link → dialog | navigate `/dashboard/entries?period=2099-01&entry=<E1 id>` | the E1 row is highlighted AND the `AttachmentAnalysisDetailDialog` is open (dialog role visible) |
| S4 | Dead deep link notice | navigate `/dashboard/entries?period=2099-01&entry=<nonexistent>` | the feature-037 not-found notice is shown; no uncaught error in console; page still rendered |
| S5 | Documents statuses | navigate `/dashboard/documents` | the seeded documents render with an "over" status badge (NF-1001) and a "within" badge (NF-1002) — asserted via the status badge data/text |
| S6a | Image route (positive) | authenticated `GET /api/attachment-analyses/<E1 analysis id>/image/p1` | 200 + `Content-Type: image/png` + non-empty body |
| S6b | Image route (auth gate) | unauthenticated `GET` of the same path | non-2xx (401/403/redirect) and the body is NOT a streamed PNG |

## Runner contract

```
uv run python -m e2e.smoke              # assumes server already running on the expected origin
uv run python -m e2e.smoke --serve      # starts pnpm preview itself, runs checks, tears down
```

- Bounded waits everywhere (no infinite hang — FR-012); default per-action timeout ≤ 30s, overall ≤ a few minutes.
- Exits non-zero on the first failed surface with a message naming the surface + expected vs actual.
- Provisions the synthetic admin (idempotent) before S1b.
- For S6 the two HTTP requests are made through Playwright's request context: S6a reuses the signed-in browser context (carries the session cookie); S6b uses a fresh context with no cookies.

## CI integration contract (`.github/workflows/ci.yml`)

A new job `e2e` (parallel to `verify`), `runs-on: ubuntu-latest`:
1. checkout, pnpm, Node 22, uv + Python 3.12 (same as `verify`).
2. `pnpm install --frozen-lockfile`.
3. `cd scripts && uv run playwright install --with-deps chromium`.
4. `pnpm db:migrate:dev` (or seed applies it).
5. `pnpm e2e:seed` (seed D1 + R2).
6. `pnpm test:py:integration` (real-D1 integration tests).
7. `pnpm test:e2e` (build + serve via `--serve`, run the smoke).

The job fails if any step fails. The existing `verify` job is unchanged.
