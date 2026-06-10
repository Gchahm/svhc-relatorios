# Implementation Plan: Derive the classification plan from D1 (remove the extract-todo.json manifest)

**Branch**: `016-derive-classify-plan-from-d1` | **Date**: 2026-06-10 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/016-derive-classify-plan-from-d1/spec.md`

## Summary

Eliminate the ephemeral per-period work manifest (`.cache/analysis/<period>.extract-todo.json`)
by deriving the classification work-plan from Cloudflare D1. The enabling change is persisting
the shared-NF grouping key (`attachments.content_hash`) at capture time, computed with the exact
algorithm the pipeline already uses (`nf_groups.content_hash`). With the key stored, grouping is
a `GROUP BY content_hash` over D1 rows instead of re-materializing and re-hashing page images on
every plan. `docs-plan` becomes a read-only "list pending work" query consumed by `classify-period`,
and `apply-extractions` derives groups (representative, members, sibling sum, group size) from D1
joins. Pre-change rows (NULL `content_hash`) keep working via a compute-from-cache fallback that
also lazily backfills the column.

## Technical Context

**Language/Version**: Python 3.12 (scraper + analysis CLIs under `scripts/`, managed by `uv`);
TypeScript 5 / Drizzle ORM for the schema + migration.
**Primary Dependencies**: scraper — `playwright`, `python-dotenv`; analysis — Python **stdlib only**;
ingestion — `wrangler` CLI (via `scripts/common/d1.py`); Drizzle Kit (`pnpm db:generate`). **No new
npm or pip dependencies.**
**Storage**: Cloudflare D1 (`DATABASE` → `fiscal-db`) and R2 (`DOCUMENTS` → `fiscal-documents`),
reached through `scripts/common/d1.py` (local Miniflare or `--remote`). Git-ignored ephemeral cache
`.cache/analysis/` holds materialized page images + per-page `.classify.json` (the manifest goes away).
**Testing**: No repo test framework (constitution III: tests OPTIONAL). Verification is manual:
equivalence of `attachment_analyses` + alerts on an existing local period, and a focused Python
smoke check of the content-hash helper + DB grouping. The analysis package is stdlib-only, so a tiny
inline `python -c` / module check is acceptable; no framework is introduced.
**Target Platform**: Cloudflare Workers (frontend, unchanged here); local dev via `uv` + `wrangler`.
**Project Type**: web app + Python pipeline (single repo; this feature touches the Python pipeline,
the Drizzle schema, and Markdown skill/agent/docs).
**Performance Goals**: Plan no longer re-hashes images when `content_hash` is populated — the plan
becomes O(rows) D1 reads instead of O(pages) byte hashing. No regression on apply/analyze.
**Constraints**: Grouping MUST stay byte-identical to today's behavior (same groups, same
reconciliation). All Python ↔ Cloudflare access stays inside `scripts/common/d1.py`. The
scraper/analysis package decoupling (feature 008) MUST be preserved — share only via `scripts/common`.
**Scale/Scope**: ~100–200 attachments per period; small. Single-repo change across ~8 files +
1 migration + 4 docs.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- **I. Type Safety & Schema Discipline** — PASS. The new `content_hash` column is added to the
  Drizzle schema (`src/db/fiscal.schema.ts`) and the migration is generated via `pnpm db:generate`
  and committed; no hand-edited migration, no ad-hoc SQL DDL. The Python upsert writes the column
  through the existing `common/d1.py` SQL generator (column list is row-key-driven, so it picks up
  the new key automatically).
- **II. Cloudflare-Native Architecture** — PASS. No new bindings; all D1/R2 access remains via
  `common/d1.py` (`query`/`upsert_tables`/`execute_sql`/`get_object`). No direct connections.
- **III. Quality Gates Before Commit** — PASS. `pnpm lint` + `pnpm format` run before commit; the
  migration + schema are committed together. No new test framework (tests OPTIONAL); manual
  equivalence verification documented in quickstart.
- **IV. Security & Auth by Default** — PASS. No routes, no auth surface, no secrets touched.
- **V. Simplicity & Incremental Delivery** — PASS. Removes a redundant intermediate file rather than
  adding abstraction. The optional `classification_status` column is explicitly **not** added (YAGNI;
  recorded in spec Assumptions). One small shared helper moves into `scripts/common` rather than
  duplicating logic.

No violations → Complexity Tracking is empty.

## Project Structure

### Documentation (this feature)

```text
specs/016-derive-classify-plan-from-d1/
├── plan.md              # This file
├── spec.md              # Feature spec
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/           # Phase 1 output (CLI/behavior contracts)
│   └── plan-and-group.md
└── checklists/
    └── requirements.md  # Spec quality checklist (from specify)
```

### Source Code (repository root)

```text
src/db/
└── fiscal.schema.ts            # + attachments.contentHash column (Drizzle)
drizzle/
└── 0008_*.sql                  # generated migration adding attachments.content_hash

scripts/
├── common/
│   ├── __init__.py             # (unchanged) det_id / now_ms
│   └── hashing.py              # NEW: pure content_hash helper, shared by scraper + analysis
├── scraper/
│   ├── runner.py               # compute + store content_hash on scrape & download-docs upsert
│   └── extractors/documentos.py# (unchanged)
└── analysis/
    ├── nf_groups.py            # content_hash re-exported from common; group_attachments by column + fallback
    ├── attachments.py          # select_work uses column-aware grouping (unchanged signature)
    ├── extractions.py          # plan_extractions → in-memory plan (no manifest); apply_extractions → DB-derived groups
    ├── images.py               # materialize + lazy-backfill content_hash for NULL rows
    ├── loader.py               # (attachments SELECT * already carries content_hash)
    └── __main__.py             # docs-plan help text / behavior (still prints a plan; writes no file)

.claude/skills/classify-period/SKILL.md   # DB-derived plan (no manifest read)
.claude/agents/analyze-docs.md            # reflect no-manifest plan
scripts/README.md                          # docs
scripts/pipeline-flow.md                   # docs (diagrams: drop manifest node)
CLAUDE.md                                  # docs (pipeline description)
```

**Structure Decision**: Single-repo change. The grouping algorithm is centralized in a new
`scripts/common/hashing.py` so the **scraper** (capture-time write) and **analysis** (read/group +
fallback) both depend on `common`, never on each other — preserving the 008 decoupling. The manifest
writer/reader is replaced by an in-memory plan object passed within the analysis process; the
`classify-period` skill obtains the same page list by invoking a plan command that prints it (no file).

## Key design decisions

1. **`docs-plan` output channel.** Today `classify-period` reads `groups[].pages[].read_path` from
   the manifest file. Replacement: `docs-plan` prints the plan as JSON to stdout (the same structure,
   minus the file). `classify-period` parses stdout instead of reading a file. `apply-extractions`
   does **not** consume that stdout — it independently re-derives the identical plan from D1 (the plan
   is a pure function of D1 + materialized images), so the two stay consistent without a shared file.
   This keeps the classify→apply seam file-free for the *plan* while leaving the per-page
   `.classify.json` seam exactly as-is (out of scope).

2. **Single plan builder.** Extract a pure `build_plan(periods, refs, filters) -> list[GroupPlan]`
   used by **both** `plan_extractions` (print) and `apply_extractions` (apply). Eliminates the
   write-then-read round-trip and guarantees byte-identical grouping between the two commands.

3. **Column-aware grouping.** `group_attachments(attachments)` keys on
   `doc["content_hash"]` when present/non-null; else falls back to `content_hash(doc["file_path"])`
   over materialized cache files (current behavior); else a `doc:{id}` singleton. Same result set as
   today on both new and legacy data.

4. **Lazy backfill.** `materialize_period_images` (which already mutates `file_path` in memory) writes
   computed `content_hash` back to D1 for rows where it is NULL, via one batched `upsert_tables`/UPDATE.
   After one run the column is populated and grouping is pure-DB. Backfill is best-effort and never
   blocks analysis.

## Complexity Tracking

No constitution violations. Table intentionally empty.
