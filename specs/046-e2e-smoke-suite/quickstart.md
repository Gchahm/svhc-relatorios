# Quickstart: Integration/E2E Smoke Suite

## Prerequisites

- `pnpm install` done; `wrangler` available (dev dep).
- Python toolchain: `cd scripts && uv sync` (or `uv run` auto-resolves). Chromium for Playwright: `cd scripts && uv run playwright install chromium` (already present in the dev container).

## Seed the local state

```bash
pnpm e2e:seed          # applies migrations + writes synthetic D1 rows + R2 images (period 2099-01)
```

Idempotent — safe to re-run. Synthetic only (no real data).

## Run the real-D1 integration tests

```bash
pnpm test:py:integration     # discovers scripts/integration_tests, runs against local Miniflare D1
```

Covers: `_merge_and_write` (atomic roll-up + state stamp + staging prune), `mark-pending` (clear + invalidate), `build-documents` (upsert then prune on re-run), feature-028 reconciliation cascade. Each asserts D1 post-state and idempotency.

## Run the browser E2E smoke

```bash
pnpm test:e2e         # builds + serves (pnpm preview), provisions synthetic admin, runs the 6 surface checks, tears down
```

Or, against an already-running `pnpm preview`:

```bash
pnpm e2e:smoke        # assumes the server is up on the expected origin
```

## The fast unit suites are unaffected

```bash
pnpm test:py          # unit only — never touches Miniflare/wrangler/browser
pnpm test:ts
```

## CI

A separate `e2e` job in `.github/workflows/ci.yml` runs the seed → integration → browser smoke on PRs and `main` pushes, in parallel with the fast `verify` job. If runtime ever exceeds budget, change only the job's `on`/`if` to move it to `main` + nightly.
