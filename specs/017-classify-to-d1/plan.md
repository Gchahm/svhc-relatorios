# Implementation Plan: Remove `.classify.json` — classify-doc-page writes per-page extractions to D1

**Branch**: `017-classify-to-d1` | **Date**: 2026-06-10 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/017-classify-to-d1/spec.md`

## Summary

Collapse the last file seam in the document-classification pipeline. Today the `classify-doc-page`
skill writes per-page extractions to `<image>.classify.json` files, which `apply-extractions` reads
via `FileExtractionProvider`. We replace that file seam with a **dedicated D1 staging table**
(`page_classifications`, one row per attachment-page): the per-page step records its extraction
through a new `record-classification` CLI command, and `apply-extractions` reads from D1 via a new
`D1ExtractionProvider`. The deterministic roll-up / reconcile / sibling fan-out / write-back is
unchanged. We also drop the dead `raw_response` (analyses) and `raw_text` (records) columns via a
committed Drizzle migration and remove their code/UI references.

The extraction-source seam already exists (`attachments.build_attachment_analysis(..., provider)`),
so the Python change is localized to the provider, the apply driver, a new staging module, one CLI
command, and the loader. The skills/agent/docs are updated to describe the DB-backed flow.

## Technical Context

**Language/Version**: Python 3.12 (analysis CLI under `scripts/`, stdlib only, run via `uv`);
TypeScript 5 / Next.js 15 (App Router) for the schema + the one UI reference; Markdown for the
Claude skills/agents.
**Primary Dependencies**: `scripts/common/d1.py` (the `wrangler`-CLI wrapper — `query` / `execute_sql`
/ `upsert_tables`); Drizzle ORM (D1 schema + migration via `pnpm db:generate`). **No new pip or npm
dependencies.**
**Storage**: Cloudflare D1 (`DATABASE` → `fiscal-db`). New table `page_classifications`; two
columns dropped (`attachment_analyses.raw_response`, `attachment_analysis_records.raw_text`). R2
(`DOCUMENTS` → `fiscal-documents`) unchanged — page images still materialized into the cache for the
vision skill.
**Testing**: No test framework configured (constitution III). Verification is the end-to-end
pipeline + `pnpm lint`/`pnpm format` + `tsc` + a local `db:migrate:dev`/`db:studio` check; a
`quickstart.md` captures the manual end-to-end check.
**Target Platform**: Cloudflare Workers (app) + local/remote Miniflare D1 (pipeline).
**Project Type**: Web app with a sidecar Python pipeline (single repo).
**Performance Goals**: No regression. The merge issues one extra D1 read per period to load the
staging rows (replacing per-page file reads); a single batched query, not per-page.
**Constraints**: `stdout` of `docs-plan` must stay pure JSON (the `classify-period` skill parses it);
any new staging read at plan time must not write to D1 (a write streams the wrangler banner to
stdout). All Python↔Cloudflare access goes through `scripts/common/d1.py`.
**Scale/Scope**: A period is ~tens to low-hundreds of attachments; the staging table is one row per
representative page (siblings reuse the representative). Trivial volume.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- **I. Type Safety & Schema Discipline** — PASS. The new table + dropped columns flow through the
  Drizzle schema (`src/db/fiscal.schema.ts`) and a generated, committed migration (`pnpm
  db:generate`); no hand-edited migration, no ad-hoc SQL for the schema change. The Python writer
  reuses `scripts/common/d1.py`'s existing escaping/upsert path (which the schema mirrors). The one
  hand-authored SQL (the new table's INSERT and the loader SELECT) goes through the sanctioned
  `d1.py` wrapper, consistent with the rest of the pipeline.
- **II. Cloudflare-Native Architecture** — PASS. Pipeline D1 access stays inside `scripts/common/d1.py`
  (the `wrangler` wrapper); the app reads D1 via Drizzle/`getDb()`. No direct connections, no new
  hardcoded endpoints. `--remote` selects production exactly as elsewhere.
- **III. Quality Gates Before Commit** — PASS. `pnpm lint` + `pnpm format` + `tsc` run before the PR.
  No test framework is added (none configured); the spec does not request automated tests, so
  verification is the end-to-end manual quickstart.
- **IV. Security & Auth by Default** — PASS. No new routes; the existing auth-gated analysis routes
  are unchanged except for dropping a column reference. No secrets touched.
- **V. Simplicity & Incremental Delivery** — PASS. One new table and one new CLI command, reusing the
  existing provider seam; the alternative (reusing analysis records with a status) is explicitly
  rejected in the spec for its read/write-cycle complexity. Delivered as priority-ordered slices
  (table+writer+reader first, cleanup second, docs third).

No violations → Complexity Tracking is empty.

## Project Structure

### Documentation (this feature)

```text
specs/017-classify-to-d1/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/           # Phase 1 output (record-classification CLI + provider seam)
│   ├── record-classification-cli.md
│   └── extraction-provider.md
├── checklists/
│   └── requirements.md  # spec quality checklist (already written by specify)
└── tasks.md             # Phase 2 output (speckit tasks — NOT created here)
```

### Source Code (repository root)

```text
src/db/
└── fiscal.schema.ts          # +page_classifications table; -raw_response, -raw_text columns
drizzle/
└── 0010_*.sql                # generated migration (new table + drop columns)

scripts/analysis/
├── page_classifications.py   # NEW: table name, det_id, frozen-contract validation,
│                             #      record_classification() write, load_*() read, D1ExtractionProvider
├── extractions.py            # apply-extractions uses D1ExtractionProvider; drop FileExtractionProvider,
│                             #      classify_path_for, CLASSIFY_SUFFIX; build_plan annotates pages `recorded`
├── attachments.py            # provider seam call → provider(attachment_id, page_label);
│                             #      drop raw_text (PageAnalysisRecord) + raw_response (AttachmentAnalysisResult)
├── loader.py                 # load page_classifications into period raw (for the provider + `recorded` flag)
└── __main__.py               # NEW `record-classification` subcommand; help text updated

.claude/skills/classify-doc-page/
├── SKILL.md                  # write via `record-classification` CLI (Bash) instead of Write tool;
│                             #      input gains attachment_id + page_label; output contract section updated
└── scripts/
    ├── validate_image.py     # unchanged (PreToolUse Read guard)
    └── validate_classify.py  # REMOVED (validation moves into the CLI); PostToolUse hook removed from SKILL.md

.claude/skills/classify-period/SKILL.md   # pass attachment_id + page_label to classify-doc-page;
                                          # DB-based completeness check (no Glob for .classify.json)
.claude/agents/analyze-docs.md            # describe DB-backed classify (no .classify.json)
.claude/agents/review-mismatch.md         # boundary note: drop ".classify.json" mention

src/app/api/attachment-analyses/[id]/route.ts            # drop rawText from select
src/app/dashboard/entries/AttachmentAnalysisDetailDialog.tsx  # drop rawText field + fallback + render

CLAUDE.md, scripts/README.md, scripts/pipeline-flow.md   # doc updates (DB-backed flow)
```

**Structure Decision**: Single repo with a Python sidecar pipeline. The change is concentrated in
`scripts/analysis/` (new staging module + provider swap + CLI command), the Drizzle schema + one
migration, the Claude skill/agent contracts, and a tiny UI cleanup. No new project, no new
dependency.

## Phase 0: Research

See `research.md`. Key resolved decisions:
1. **Storage shape** — dedicated `page_classifications` table (resolved in spec; rationale carried
   into research with the rejected alternative).
2. **How the page key is supplied** — the orchestrator passes `attachment_id` + `page_label` to
   `classify-doc-page` (the page-image filename is named by *entry*, not attachment), and the merge
   looks up by the same (attachment_id, page_label) pair.
3. **Where validation lives** — moves from the PostToolUse file hook into the `record-classification`
   CLI (the skill no longer writes a file), reusing the exact frozen contract.
4. **Completeness check** — `docs-plan` annotates each planned page with a `recorded` boolean
   (DB-derived); `classify-period` re-dispatches any page not yet recorded.
5. **Dropping dead columns** — confirmed unused by the Claude flow; removed via a generated Drizzle
   migration; the only consumers are the schema, a UI fallback, and the Python dataclasses.

## Phase 1: Design & Contracts

- `data-model.md` — the new `page_classifications` entity (fields, key, lifecycle), the dropped
  columns, and how the provider maps (attachment_id, page_label) → fields/error.
- `contracts/record-classification-cli.md` — the `python -m analysis record-classification` command
  surface (args, stdin/inline JSON, validation, exit codes, idempotency, `--remote`).
- `contracts/extraction-provider.md` — the updated provider seam signature
  `(attachment_id, page_label) -> (fields|None, error|None)` and the D1-backed implementation
  contract.
- `quickstart.md` — the end-to-end manual verification (classify → clear scratch → apply → analyze →
  mismatches; equivalence to baseline; cache holds no `.classify.json`).
- Agent context updated via `update-agent-context.sh`.

## Complexity Tracking

No constitution violations — no entries.

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| (none)    | —          | —                                    |
