# Implementation Plan: Vision-analyze every page of a document, with per-page parsed results

**Branch**: `003-vlm-analyze-all-pages` | **Date**: 2026-06-05 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/003-vlm-analyze-all-pages/spec.md`

## Summary

Today the VLM document-analysis pass (`scripts/scraper/analise/documentos.py`) analyzes only
the **first** page image of each document and stores the page-1 VLM text as an opaque
`raw_response` string. This blinds the audit to later pages and emits false amount mismatches
when a document bundles heterogeneous artifacts (invoice gross vs. net vs. paid).

This feature: (1) iterates **every** page image, running one VLM pass per page; (2) introduces a
normalized **`document_analysis_records`** table — one row per page per analysis kind — carrying
the page's artifact role and parsed JSON response, nested under its document analysis in the
period JSON and flattened on D1 import; (3) makes the document-level roll-up heterogeneity-aware
so `amount_match` validates against the **paid/net** value when a payment artifact is present;
and (4) fixes the importer's `escapeSQL` to JSON-serialize object/array values instead of
corrupting them to `"[object Object]"`. The legacy `raw_response` column is retained as nullable
legacy and no longer populated with per-page detail.

## Technical Context

**Language/Version**: Python 3.11+ (scraper/analysis pass); JavaScript/Node (D1 importer); TypeScript (Drizzle schema)
**Primary Dependencies**: `mlx_vlm` (Qwen2.5-VL, macOS/MLX) for the VLM pass; Drizzle ORM + `wrangler d1` for persistence
**Storage**: Cloudflare D1 (SQLite) via Drizzle; intermediate scraped period JSON in `data/scrape/<period>.json`
**Testing**: None configured — verification is by running `analyze-docs` on the evidence period and inspecting JSON + D1 rows (per Constitution Principle III, no test framework is mandated)
**Target Platform**: VLM pass runs on macOS/MLX; importer + D1 run via Node/wrangler; app runs on Cloudflare Workers
**Project Type**: Single web app (Next.js) with a companion Python scraper/analysis pipeline under `scripts/scraper/`
**Performance Goals**: One VLM call per page — N-page document now costs N calls instead of 1; acceptable for a batch offline pass (no latency SLO)
**Constraints**: A single bad/unreadable/unparseable page MUST NOT abort the document; per-document write-back must remain crash-safe (partial-progress preserving)
**Scale/Scope**: Hundreds of documents per period; documents range 1–~6 pages

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Assessment |
|-----------|------------|
| I. Type Safety & Schema Discipline | **PASS** — the new `document_analysis_records` table is added to `src/db/fiscal.schema.ts` and the migration is produced via `pnpm db:generate` and committed under `drizzle/`. No hand-edited SQL or migration. `auth.schema.ts` untouched. |
| II. Cloudflare-Native Architecture | **PASS** — no new runtime DB access path; import goes through the existing `wrangler d1 execute` flow. No `getCloudflareContext()` build/runtime coupling introduced. |
| III. Quality Gates Before Commit | **PASS** — `pnpm lint` + `pnpm format` run before commit; TS/JS changes formatted. No tests mandated (no framework); manual verification against the evidence period documented in quickstart. |
| IV. Security & Auth by Default | **N/A** — no new routes, no auth surface, no secrets; offline batch + import only. |
| V. Simplicity & Incremental Delivery | **PASS** — exactly one new table, reusing existing dataclass/`to_dict`/importer patterns. Per-page records are the minimum normalization needed; no speculative `analysis_type` implementations beyond `page_extraction`. Delivered as independently testable P1 slices. |

**Result**: All gates pass. Complexity Tracking is empty (no deviations).

## Project Structure

### Documentation (this feature)

```text
specs/003-vlm-analyze-all-pages/
├── plan.md              # This file
├── spec.md              # Feature spec (already written)
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/           # Phase 1 output (data contracts, not REST)
│   ├── page-extraction.schema.json   # VLM per-page JSON output contract
│   └── period-json.md                # nested analysis_records shape in period JSON
└── checklists/
    └── requirements.md  # from specify phase
```

### Source Code (repository root)

```text
scripts/
├── scraper/
│   └── analise/
│       └── documentos.py        # MODIFY: per-page loop, PageAnalysisRecord model,
│                                #         heterogeneity-aware roll-up, prompt update
└── import-to-d1.mjs             # MODIFY: escapeSQL object/array branch; flatten nested
                                 #         analysis_records into the new table on import

src/db/
└── fiscal.schema.ts             # MODIFY: add documentAnalysisRecords table + relations

drizzle/
└── 0006_*.sql                   # NEW: generated migration for the new table
```

**Structure Decision**: This is the existing single-repo layout (Next.js app + companion Python
pipeline). No new top-level projects. The change touches four existing concerns: the Python
analysis pass, the TS Drizzle schema, a generated migration, and the Node importer. The new
entity is a normalized child table of `document_analyses`; per-page detail moves out of the
`document_analyses.raw_response` string into it.

## Phase 0 — Research

See [research.md](./research.md). Key decisions resolved:

- **Period-JSON shape for records**: nested array `analysis_records` inside each
  `document_analyses` object (matches the spec's "nested under their document analysis"); the
  importer flattens them into the top-level table.
- **New table name / shape**: `document_analysis_records` with FK `document_analysis_id`
  (non-unique → many per document), `analysis_type`, `page_index` + `page_label`,
  `artifact_role`, `response` (TEXT JSON), `raw_text`, `parse_error`, `analyzed_at`.
- **`raw_response` disposition**: retained as nullable legacy column on `document_analyses`,
  no longer populated with per-page detail (avoids a destructive migration; honors FR-010).
- **Roll-up amount-match rule**: prefer paid (payment proof) → net (invoice) → gross when a
  payment artifact is present; fall back to single representative value otherwise.
- **Prompt**: extend `EXTRACT_PROMPT` to classify `papel_artefato` (artifact role) and capture
  gross/net/paid (`valor_bruto`/`valor_liquido`/`valor_pago`) in addition to `valor_total`.

## Phase 1 — Design & Contracts

- [data-model.md](./data-model.md) — the new `document_analysis_records` entity, the unchanged
  `document_analyses` roll-up, field-level definitions, and roll-up derivation rules.
- [contracts/page-extraction.schema.json](./contracts/page-extraction.schema.json) — the JSON
  contract the VLM must return per page (the `page_extraction` response).
- [contracts/period-json.md](./contracts/period-json.md) — the nested `analysis_records` shape
  in the period JSON and how the importer flattens it.
- [quickstart.md](./quickstart.md) — how to run `analyze-docs` + import and verify acceptance
  against the evidence document.

**Post-design Constitution re-check**: still all PASS. The design adds one normalized table and
reuses existing serialization/import patterns; no new abstractions or dependencies; no violations
to record in Complexity Tracking.

## Complexity Tracking

> No constitutional violations — table intentionally empty.

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| — | — | — |
