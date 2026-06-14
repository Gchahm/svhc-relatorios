---
name: local-db-persist-selector
description: Two isolated local DBs via SVHC_WRANGLER_PERSIST persist dir; every direct wrangler shell-out (even outside d1.py) must honor it
metadata:
  type: project
---

Local Miniflare has TWO isolated DBs (feature 061 / issue #107): **staging** = wrangler default
`.wrangler/state` (the human; every normal command), **test** = `.wrangler/state-test` (agents'
test/seed/e2e suites, wipe-and-reseed freely). Selector = env var **`SVHC_WRANGLER_PERSIST`**, read by
`common/d1.py:_persist_args(target)` → appends `--persist-to <dir>` to every LOCAL wrangler shell-out
(relative resolves against `_REPO_ROOT`; never for `--remote`; unset ⇒ staging default). The four test
npm scripts (`test:py:integration`/`e2e:seed`/`e2e:smoke`/`test:e2e`) prefix it; `e2e/server.py`
forwards `--persist-to` to the preview's `wrangler dev`. `db:migrate:test`/`preview:test` carry the
explicit flag.

**Gotcha (cost me a CI red):** a wrangler call that does NOT go through `d1.py`'s read/write helpers
will silently ignore the selector and hit staging. `e2e/seed.py:_apply_migrations` shells out
`wrangler d1 migrations apply DATABASE --local` directly — it migrated `.wrangler/state` while the
subsequent `d1.py` upserts landed in `.wrangler/state-test`, so on a FRESH runner the test DB had no
schema → `no such table: scrape_runs`. It passed locally only because I'd pre-run `db:migrate:test`.

**Why:** the selector is plumbed through `d1.py`, not magically global. **How to apply:** any new direct
wrangler subprocess in `scripts/` must append `d1._persist_args("local")` itself; and verify against a
**fresh/empty** test dir (move `.wrangler/state-test` aside first), not a pre-migrated one — CI starts
clean. The only direct shell-out outside `d1.py` today is `seed.py:_apply_migrations` (now fixed).

Verifying isolation: write a sentinel into staging (`wrangler d1 execute DATABASE --local --command
"…"`), `pnpm e2e:seed` + suites, confirm the staging sentinel + row counts survive. `.wrangler` (hence
`state-test`) is already gitignored. Known pre-existing quirk: `drizzle.config.ts:getLocalD1DB` picks the
first `.sqlite` under `.wrangler` recursively — `db:studio:test` deferred for that reason.
