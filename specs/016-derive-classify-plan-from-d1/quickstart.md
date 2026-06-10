# Quickstart: Derive the classification plan from D1

## What changed for a user

- The pipeline no longer writes `.cache/analysis/<period>.extract-todo.json`. The plan is derived
  from D1 each time.
- Attachments now carry a `content_hash` (shared-NF grouping key), written at scrape time.
- Commands are the same; `docs-plan` now prints the plan to stdout instead of writing a file.

## Apply the schema migration (local)

```bash
pnpm db:generate          # produces drizzle/0008_*.sql adding attachments.content_hash
pnpm db:migrate:dev       # applies locally
# production: pnpm db:migrate:prod
```

> Sandbox note: if `pnpm db:generate` fails on an ignored-build sandbox, call the binary directly
> (`node_modules/.bin/drizzle-kit generate`) — see project memory.

## Run the pipeline (local)

```bash
cd scripts

# Plan: prints the JSON plan to stdout, writes NO file
uv run python -m analysis docs-plan --periodo 2025-12

# Classify (Claude): the classify-period skill runs docs-plan and reads its stdout
#   then fans pages out to classify-doc-page

# Merge → roll-up + reconcile (groups derived from D1)
uv run python -m analysis apply-extractions --periodo 2025-12

# Checks → alerts
uv run python -m analysis analyze --periodo 2025-12

# Terse mismatch summary
uv run python -m analysis mismatches --periodo 2025-12
```

## Verify (acceptance)

```bash
# SC-001 / FR-007: no manifest written, no code references it
ls scripts/../.cache/analysis/*.extract-todo.json 2>/dev/null && echo "FAIL: manifest exists" || echo "OK: no manifest"
grep -rn "extract-todo" scripts .claude && echo "FAIL: references remain" || echo "OK: no references"

# SC-002: capture populates the hash (after a --download-docs scrape, or lazy backfill)
npx wrangler d1 execute DATABASE --command \
  "SELECT count(*) total, count(content_hash) hashed FROM attachments" --json --local

# SC-003: equivalence — diff attachment_analyses + alerts for a period against a pre-change snapshot
#   (capture a snapshot before checking out the branch, then compare row-by-row)
```

## Equivalence check (recommended before PR)

1. On `main` (pre-change), snapshot a period:
   `npx wrangler d1 execute DATABASE --command "SELECT * FROM attachment_analyses ORDER BY attachment_id" --json --local > /tmp/before.json`
   (and the same for `alerts`).
2. On the feature branch, re-run `apply-extractions` + `analyze` for that period and snapshot again to
   `/tmp/after.json`.
3. Diff: groups, `amount_match`/`vendor_match`/`date_match`, and `duplicate_billing` alerts must match.

## Notes

- Legacy rows (NULL `content_hash`) still group correctly via the compute-from-cache fallback and are
  backfilled lazily during materialization.
- No new dependencies. Analysis stays Python-stdlib-only; the shared hash lives in `scripts/common`.
