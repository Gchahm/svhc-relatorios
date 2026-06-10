# Contract: DB-derived plan & grouping (no manifest)

This feature has no HTTP API surface. The "contracts" are the behavioral contracts of the
pipeline functions/CLIs that change, plus the schema column. Each is independently verifiable.

## C1 — `scripts/common/hashing.py:content_hash(file_path: str) -> str | None`

- **Input**: `;`-joined page file paths (local). **Output**: md5 hexdigest, or `None` if no pages
  or any page unreadable.
- **Contract**: byte-for-byte identical to the pre-move `nf_groups.content_hash` (same chunking,
  same `:{size}:` per-page length delimiter, same page order). `nf_groups.content_hash` becomes a
  re-export of this symbol — existing imports (`from .nf_groups import content_hash`) keep working.
- **Stdlib-only** (honors `common`'s contract).

## C2 — Schema: `attachments.content_hash`

- Drizzle column `contentHash: text("content_hash")` exists; `pnpm db:generate` produces a committed
  migration adding `content_hash text` to `attachments`; `pnpm db:migrate:dev` applies cleanly.
- Verifiable: `PRAGMA table_info(attachments)` lists `content_hash`.

## C3 — Capture writes the hash (scraper)

- `run_scrape --download-docs` and `download-docs`: after downloading an attachment's pages, the
  upserted attachment row carries `content_hash = content_hash(";".join(local_page_paths))`.
- An attachment with no downloaded pages keeps `content_hash = NULL`.
- Verifiable post-capture: `SELECT content_hash FROM attachments WHERE id=…` is non-NULL for
  attachments with pages; two byte-identical attachments share the value.

## C4 — `group_attachments(attachments) -> dict[str, list[dict]]` (column-aware)

- Keys each attachment by, in order: `content_hash` column when present & non-null; else
  `content_hash(file_path)` over materialized files (legacy fallback); else `doc:{id}`.
- **Contract**: for any dataset, the returned group partition equals the legacy file-hash partition
  (same groups, same members) — on both new and legacy data.
- Same public signature as today; `select_work` and the duplicate-billing check need no signature change.

## C5 — `docs-plan` (CLI) prints the plan, writes no file

- `python -m analysis docs-plan --periodo <p> [filters] [--remote]` prints the plan envelope (see
  data-model) as JSON to stdout and writes **no** `*.extract-todo.json`.
- "Nothing to extract" path: prints the same human message as today and an empty/ë absent `groups`,
  still writing no file.
- Filters (`--min-amount`, `--limit`, `--reanalyze`, `--attachment-id`, `--entry-id`) behave exactly
  as today (targeting implies re-analysis).
- Verifiable: after running, `ls .cache/analysis/*.extract-todo.json` finds nothing; stdout parses to
  the envelope.

## C6 — `apply-extractions` derives groups from D1

- `python -m analysis apply-extractions --periodo <p> [--remote]` re-derives the same groups via
  `build_plan(...)` from D1 + materialized images (not from a file) and writes `attachment_analyses`
  (+ flattened records) via the existing delete-then-insert.
- **Contract**: output rows are identical in shape and values to the pre-change flow for the same
  per-page `.classify.json` inputs (same representative roll-up, same sibling fan-out, same
  `amount_match` group reconciliation).
- When run without a period filter, it processes the periods present in D1 (replacing the old
  "periods that have a manifest" discovery).

## C7 — Lazy backfill

- During materialization, attachments with NULL `content_hash` whose pages were materialized get the
  computed hash written back to D1 (UPDATE only the `content_hash` column; never overwrite non-NULL;
  never touch other columns). Best-effort: a backfill failure logs and does not abort analysis.
- Verifiable: after one `apply-extractions`/`mismatches` run over a legacy period, previously-NULL
  `content_hash` values are populated.

## C8 — `classify-period` skill consumes the printed plan

- The skill runs `docs-plan` and parses its **stdout JSON** (not a file) to get
  `groups[].pages[].read_path`, then fans out `classify-doc-page`. No file read of
  `*.extract-todo.json`.

## C9 — No references to `extract-todo.json` remain

- `grep -r "extract-todo" scripts .claude` returns nothing (code, skill, agent). Docs may reference it
  only in a historical/"removed" note if at all.
