# Quickstart: Two local databases (test vs staging)

This repo now keeps **two isolated local databases**:

- **Staging** — wrangler's default `.wrangler/state`. Used by every normal local command (`pnpm dev`,
  `pnpm preview`, `pnpm db:migrate:dev`, `pnpm db:studio:dev`). This is the human's manual-testing DB.
  Nothing about these commands changed.
- **Test** — `.wrangler/state-test`. Used by the automated test/seed/e2e tooling, which wipes and
  reseeds it freely. Agents can run the full suite without touching staging.

The switch is one env var: **`SVHC_WRANGLER_PERSIST`**. Set it to a persist directory and every
**local** wrangler call (D1 + R2 + KV) for that process goes there. Unset ⇒ staging default.
`--remote` (production) is never affected.

## Run the agent test suite (isolated — does not touch staging)

```bash
pnpm e2e:seed              # seed the synthetic 2099-01 period into the TEST DB
pnpm test:py:integration  # real-D1 integration tests against the TEST DB
pnpm test:e2e             # build + serve + browser smoke against the TEST DB
```

These scripts self-bootstrap the test DB (the harness/seed apply migrations on first run). For an
explicit migrate:

```bash
pnpm db:migrate:test      # create/migrate .wrangler/state-test
```

## Eyeball the seeded test DB

```bash
pnpm e2e:seed && pnpm preview:test   # preview the app served against the TEST DB
```

## Run the real pipeline against the test DB manually

The default for any non-test command is **staging**. To point a manual `python -m scraper/analysis`
run at the test DB, set the var yourself:

```bash
SVHC_WRANGLER_PERSIST=.wrangler/state-test python -m analysis analyze --periodo 2099-01
```

(Without it, a manual local pipeline run hits **staging** — an accepted, documented boundary.)

## Verify isolation (acceptance SC-003)

```bash
# 1. Write a sentinel into STAGING (default dir) and seed TEST.
npx wrangler d1 execute DATABASE --local --command \
  "INSERT OR REPLACE INTO scrape_runs (id, periodo, status) VALUES ('sentinel-staging','1900-01','ok')"
pnpm e2e:seed

# 2. Run the full agent suite (writes only the test dir).
pnpm test:py:integration && pnpm test:e2e

# 3. Confirm the staging sentinel survived untouched.
npx wrangler d1 execute DATABASE --local --command \
  "SELECT id FROM scrape_runs WHERE id='sentinel-staging'"   # → still present
```

## Known interaction (pre-existing)

`pnpm db:studio:dev` resolves its sqlite file via a recursive first-match search under `.wrangler`
(`drizzle.config.ts:getLocalD1DB`). This is a pre-existing quirk unrelated to this feature. Because
`.wrangler/state-test` is created only on demand (and gitignored), a checkout that never runs the test
scripts is unaffected. A `db:studio:test` variant is intentionally deferred (see research R8); inspect
the test DB with `pnpm preview:test` instead.
