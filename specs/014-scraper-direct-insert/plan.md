# Implementation Plan: Scraper and analysis operate directly on the database

**Branch**: `014-scraper-direct-insert` | **Date**: 2026-06-09 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/014-scraper-direct-insert/spec.md`

## Summary

Today the Python scraper writes a per-period JSON file (`data/scrape/<period>.json`) plus a folder of page images; a separate Node step (`import-to-d1.mjs`) turns that JSON into SQL and runs `wrangler d1 execute`, and `upload-images-to-r2.mjs` pushes the images to R2. The analysis/classification pipeline reads and rewrites that same JSON and writes `.classify.json` siblings next to the images.

This feature collapses that into a direct path: the scraper writes the structured ledger rows **straight into Cloudflare D1** (local by default, remote on request) and uploads page images **straight into R2** during the same run, with no period JSON resting on disk. The analysis/classification pipeline is re-pointed at the same structure — it **loads period data from D1**, **materializes page-image bytes from R2** into an ephemeral local cache for vision + content-hashing, and **writes its results (`document_analyses`, `document_analysis_records`, `alerts`) back into D1**. The old file-based path (period JSON, `import-to-d1.mjs`, file-based analysis) is removed.

The mechanism that makes this possible without new dependencies or a REST token is the **`wrangler` CLI**, which the project already uses for D1 import and migrations: Python shells out to `wrangler d1 execute … --json` (reads) / `--file=…` (batched upserts) and `wrangler r2 object get/put`, with a single `--local`/`--remote` target threaded through scrape and analysis. The existing SQL-generation logic (`escapeSQL`, `TABLE_ORDER`, `INSERT OR REPLACE`, `analysis_records` flattening) is ported from `import-to-d1.mjs` into a shared Python module. The D1 schema, table names, columns, and deterministic IDs are unchanged.

## Technical Context

**Language/Version**: Python 3.12 (scraper under `scripts/scraper/`, analysis under `scripts/analysis/`, managed by `uv`); Node 22 for the `wrangler` CLI; TypeScript 5 / Next.js 15 frontend (unchanged — it already reads D1 + R2).
**Primary Dependencies**: Existing only — scraper: `playwright`, `python-dotenv`; analysis: Python **stdlib only**; ingestion mechanism: `wrangler` CLI (already a dev dependency). **No new npm or pip dependencies.**
**Storage**: Cloudflare D1 (`DATABASE` binding, `fiscal-db`) and Cloudflare R2 (`DOCUMENTS` binding, `fiscal-documents`), both reached via `wrangler` (local Miniflare state or `--remote`). An ephemeral, git-ignored local cache holds materialized page images + per-run scratch for vision; it is never a source of truth.
**Testing**: Repo has no test framework configured (constitution: tests OPTIONAL). Verification is a manual local round-trip (scrape → query D1 → classify → analyze → view) plus a parity check against a JSON-era period.
**Target Platform**: Linux/macOS developer shells (scrape/analysis CLIs) + Cloudflare Workers (the deployed app, unchanged).
**Project Type**: Single repo — Python CLI scripts + a Next.js app. This feature is almost entirely in the Python scripts; the app is unaffected.
**Performance Goals**: Parity with today's import. Per period, ledger upserts execute as a single batched `wrangler d1 execute --file` call (same as `import-to-d1.mjs`); image upload is one `wrangler r2 object put` per page (same as `upload-images-to-r2.mjs`). No regression versus the two-step flow.
**Constraints**:
- D1 is reachable from Python **only** through the `wrangler` CLI (no public D1 REST API, no `CLOUDFLARE_API_TOKEN`/`account_id` in the repo). Remote operations rely on the operator's existing `wrangler` auth — same trust model as `import-to-d1.mjs` and `db:migrate:prod` today.
- Claude vision (`classify-doc-page`) reads a **local file path**; page bytes must be materialized from R2 before classification and before NF content-hashing.
- D1 schema is unchanged; Python-generated SQL derives column names from row dicts (as `import-to-d1.mjs` does) to avoid drift.
- The `documents.file_path` ↔ R2 object-key contract (`src/lib/r2.ts:objectKeyFromFilePath`) must keep agreeing so the frontend serves images unchanged.
**Scale/Scope**: A period is on the order of hundreds of ledger rows and ~500 page images (~2–3 MB of structured data). Multiple periods may exist.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- **I. Type Safety & Schema Discipline** — PASS. No D1 schema change (same tables/columns/IDs); therefore no Drizzle migration and no `auth.schema.ts` touch. Python emits `INSERT OR REPLACE` with column names taken from the row dicts, exactly as `import-to-d1.mjs` does, so code and schema cannot silently diverge. If any frontend TS is touched (not expected), it must type-check cleanly.
- **II. Cloudflare-Native Architecture** — PASS. The *application's* DB access stays behind `getDb()`/`getDocumentsBucket()` and is untouched. The *scripts* legitimately reach D1/R2 through the `wrangler` CLI — the same sanctioned external path the repo already uses for `import-to-d1.mjs`, `upload-images-to-r2.mjs`, and `db:migrate:*`. No direct connection construction, no new endpoints/credentials; bindings remain declared in `wrangler.toml`.
- **III. Quality Gates Before Commit** — PASS (process). Run `pnpm lint` + `pnpm format` before commit; any touched TS conforms to Prettier settings. Manual verification of the running app accompanies the change (image viewing + analyses still render).
- **IV. Security & Auth by Default** — PASS. No new routes or public surface. Writing to **remote** D1/R2 requires the operator's `wrangler` auth (unchanged trust model); the CLIs default to **local** and must announce the target before any remote write, so production is never hit by accident. No secrets enter source or the bundle.
- **V. Simplicity & Incremental Delivery** — PASS with care. This is a sizeable refactor, so it is sequenced into independently shippable slices (see Phasing) ordered by the spec's P1→P2 priorities, and it deliberately **reuses** the existing SQL-gen logic and the single `load_all_periods` seam rather than introducing new abstractions. The one genuinely new internal abstraction — a thin Python D1/R2 access wrapper — is justified by a concrete present need (Python has no other way to reach D1) and is recorded below.

No violations require Complexity Tracking entries.

## Project Structure

### Documentation (this feature)

```text
specs/014-scraper-direct-insert/
├── plan.md              # This file
├── spec.md              # Feature spec (already written)
├── research.md          # Phase 0 output (this run)
├── data-model.md        # Phase 1 output (this run)
├── quickstart.md        # Phase 1 output (this run)
├── contracts/           # Phase 1 output (this run)
│   ├── cli.md                       # scrape + analysis command surfaces & target flag
│   ├── python-d1-r2-access.md       # the shared wrangler-backed access module
│   └── period-loader-and-writeback.md  # D1-backed load_all_periods + result writeback
├── checklists/
│   └── requirements.md  # spec-quality checklist (already passing)
└── tasks.md             # Phase 2 output (speckit tasks — NOT created here)
```

### Source Code (repository root)

```text
scripts/
├── common/
│   ├── __init__.py            # det_id() etc. (unchanged)
│   └── d1.py                  # NEW: wrangler-backed D1/R2 access + SQL generation
│                              #      (target=local|remote; execute_sql/query/put_object/get_object;
│                              #       escapeSQL/TABLE_ORDER/INSERT-OR-REPLACE ported from import-to-d1.mjs)
├── scraper/
│   ├── __main__.py            # CHANGED: add --remote (target) to `scrape`/`download-docs`; drop --output-dir as the resting place
│   ├── runner.py              # CHANGED: run_scrape upserts period rows to D1 instead of write_text; uploads images to R2
│   └── documentos.py          # CHANGED: image download streams to R2 (+ ephemeral local copy for the run); sets file_path to R2-key form
├── analysis/
│   ├── __main__.py            # CHANGED: add --remote (target) to every command; thread to loader + writeback
│   ├── loader.py              # CHANGED: load_all_periods reads from D1 (assembles the same PeriodData/raw shape)
│   ├── extractions.py         # CHANGED: apply-extractions writeback → D1 upsert; manifest read_paths point at materialized cache
│   ├── __init__.py            # CHANGED: run_analysis writes alerts to D1 instead of JSON
│   ├── verdicts.py            # MOSTLY UNCHANGED: verdicts/loop-state stay as ephemeral local scratch (allowed)
│   ├── images.py              # NEW (small): materialize a period's/scope's page images from R2 into the cache dir
│   ├── nf_groups.py           # UNCHANGED logic: hashes the materialized local image bytes
│   └── checks/*.py            # UNCHANGED: operate on in-memory PeriodData
├── import-to-d1.mjs           # REMOVED (logic ported to scripts/common/d1.py)
└── upload-images-to-r2.mjs    # REMOVED (logic folded into the scrape run + scripts/common/d1.py)

.claude/
├── skills/
│   ├── classify-doc-page/SKILL.md      # UNCHANGED behavior (writes .classify.json next to the image path it is given — now a cache path)
│   ├── classify-period/SKILL.md        # CHANGED: note manifest read_paths resolve to the R2-materialized cache
│   └── improve-classification/SKILL.md # CHANGED: pass the --remote target through analyze/review/fix
└── agents/
    ├── analyze-docs.md          # CHANGED: runs classify-period → apply/analyze/mismatches with the target flag; images come from R2
    ├── review-mismatch.md       # CHANGED: page_refs read_path resolves to the materialized cache image
    └── fix-mismatch.md          # CHANGED: scoped verify commands carry the target flag

src/lib/r2.ts                    # UNCHANGED (objectKeyFromFilePath must keep matching the file_path the scraper now writes)
package.json                     # CHANGED: drop dead import/upload script references if any; (CLIs run via uv, not pnpm)
.gitignore                       # CHANGED: ignore the ephemeral analysis cache dir
```

**Structure Decision**: Single repo, change concentrated in `scripts/` (Python). The new `scripts/common/d1.py` is the one new module — the shared, `wrangler`-backed access + SQL-generation layer that both the scraper and the analysis CLI use, replacing the two retired `.mjs` scripts. `loader.py` remains the single load seam; only its *source* flips from files to D1. The Next.js app and `src/lib/r2.ts` are untouched because they already read the new structure.

## Phasing (incremental, priority-ordered)

Each slice is independently shippable and demonstrable; they map to the spec's user stories.

1. **Access layer (foundation for US1/US2/US3)** — `scripts/common/d1.py`: target resolution (`local` default / `remote`), `execute_sql(sql, target)` (batched upsert via temp `.sql` file), `query(sql, target) -> list[dict]` (via `--json`), `put_object`/`get_object` (R2), and the ported SQL generation (escaping, `TABLE_ORDER`, `INSERT OR REPLACE`, `analysis_records` flatten). No behavior change yet; unit-exercised by a tiny local round-trip.
2. **US1 + US2 — scraper writes ledger straight to D1** — `runner.py` upserts the in-memory `period_data` tables via the access layer; `__main__.py` gains `--remote`; default local; per-table row summary printed; period JSON no longer written.
3. **US1 + US2 — page images straight to R2 during the scrape** — `documentos.py` uploads each downloaded page to R2 at key `<period>/<basename>` and sets `documents.file_path` to the `;`-joined R2-key form; nothing rests in the data folder.
4. **US3 — analysis reads from D1** — `loader.py:load_all_periods` queries D1 (scoped by period) and assembles the identical `PeriodData`/`raw` dicts; `__main__.py` threads `--remote` into the loader.
5. **US3 — vision/grouping read images from R2** — `analysis/images.py` materializes the scope's page bytes from R2 into the ephemeral cache; `docs-plan` manifest and `summarize_mismatches` `page_refs` emit cache `read_path`s; NF content-hash and `classify-doc-page` read those cache files; `.classify.json`/manifest/verdicts stay as ephemeral local scratch in the cache.
6. **US3 — analysis writes results to D1** — `apply-extractions` (`_merge_and_write`) and `analyze` (`run_analysis`) upsert `document_analyses` / `document_analysis_records` / `alerts` into D1 instead of rewriting JSON; the loop skills/agents pass the target through.
7. **Cleanup (FR-014)** — remove `import-to-d1.mjs`, `upload-images-to-r2.mjs`, any period-JSON write paths and now-dead `--output-dir`/file flags; update docs (`CLAUDE.md`, agent/skill notes) and `.gitignore`.

## Complexity Tracking

No constitution violations require justification. The single new abstraction (`scripts/common/d1.py`) is recorded here for transparency, not as a violation:

| Addition | Why Needed | Simpler Alternative Rejected Because |
|----------|-----------|--------------------------------------|
| `scripts/common/d1.py` (wrangler-backed D1/R2 access + SQL gen) | Python has no other sanctioned way to reach D1/R2; both scraper and analysis need read+write against local/remote | Writing the local Miniflare SQLite file directly is brittle (internal path/WAL/schema details) and cannot reach remote; duplicating SQL-gen in two places (scraper + analysis) would drift — one shared module is the minimal seam |
