# Implementation Plan: Rename "documents" → "attachments"

**Branch**: `015-rename-documents-attachments` | **Date**: 2026-06-09 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/015-rename-documents-attachments/spec.md`

## Summary

Rename the per-entry, multi-page downloaded bundle from "document" to **attachment** across the whole stack — D1 schema (Drizzle), the TypeScript app (queries, API routes, UI), and the Python scrape/analysis pipeline — and free the name **document** for a future N:N real-document entity. This is a **behavior-preserving rename** (FR-003): same alerts, roll-ups, and mismatch output. Data is handled **destructively** (drop & re-scrape, FR-008) — a single Drizzle migration recreates the renamed tables; no in-place data migration. **Rename-only** (FR-009): no new `documents` table/join/check is created.

## Technical Context

**Language/Version**: TypeScript 5 / React 19 / Next.js 15 (App Router); Python 3.12 (stdlib only) for the pipeline  
**Primary Dependencies**: Drizzle ORM (D1), better-auth, shadcn/ui, lucide-react, @tanstack/react-virtual; `wrangler` CLI; Python stdlib + `playwright` (scraper). **No new dependencies.**  
**Storage**: Cloudflare D1 (`DATABASE` binding, `fiscal-db`) and R2 (`DOCUMENTS` binding, `fiscal-documents`) — the R2 binding/bucket name is **retained** (storage infra; spec Assumptions). Page-image object-key derivation is unchanged.  
**Testing**: No automated test framework (constitution III); verification is a full pipeline run + UI inspection on a period (quickstart.md).  
**Target Platform**: Cloudflare Workers via OpenNext.  
**Project Type**: Web (Next.js frontend + API routes) + a Python CLI pipeline.  
**Performance Goals**: N/A (pure rename; no behavioral change).  
**Constraints**: Schema changes flow through `pnpm db:generate` + a committed migration (constitution I); `pnpm lint` + `pnpm format` must pass before commit (constitution III).  
**Scale/Scope**: ~8 TS files, ~10 Python files, 1 new migration, 4 agent/skill docs, 3 project docs.

## Constitution Check

_GATE: Must pass before Phase 0 research. Re-check after Phase 1 design._

- **I. Type Safety & Schema Discipline** — PASS. The rename is expressed in `src/db/fiscal.schema.ts` and a generated migration via `pnpm db:generate`; no hand-edited migrations, no ad-hoc SQL in app code. `auth.schema.ts` is untouched.
- **II. Cloudflare-Native Architecture** — PASS. DB access stays via `getDb()`; R2 via the retained `DOCUMENTS` binding. No new bindings; no build/runtime coupling changes.
- **III. Quality Gates Before Commit** — PASS. `pnpm lint` + `pnpm format` run before commit; manual full-pipeline verification accompanies the change (no test framework to add).
- **IV. Security & Auth by Default** — PASS. Renamed API routes keep their existing auth gating; no new public exposure; auth tables out of scope.
- **V. Simplicity & Incremental Delivery** — PASS. Strictly a rename (YAGNI): no new abstractions, no new tables, no future-feature scaffolding. Delivered as one coherent, behavior-preserving slice.

No violations → Complexity Tracking not required.

## Project Structure

### Documentation (this feature)

```text
specs/015-rename-documents-attachments/
├── plan.md              # This file
├── research.md          # Rename boundary decisions (keep-vs-rename)
├── data-model.md        # Exact table/column/identifier rename map
├── quickstart.md        # Behavior-preserving verification steps
├── contracts/
│   └── routes.md        # Renamed API route paths (no new endpoints)
├── checklists/
│   └── requirements.md  # Spec quality checklist (from specify)
└── tasks.md             # Phase 2 output (speckit tasks)
```

### Source Code (repository root)

```text
src/
├── db/fiscal.schema.ts                       # tables/columns/indexes/relations renamed
├── lib/r2.ts                                  # comments retargeted; binding/accessor retained
└── app/
    ├── api/attachment-analyses/               # renamed from api/document-analyses/
    │   ├── route.ts
    │   └── [id]/{route.ts, pages/route.ts, image/[page]/route.ts}
    └── dashboard/
        ├── document-analyses/page.tsx         # legacy redirect shim — RETAINED (old bookmarks)
        └── entries/{EntriesClient.tsx, AttachmentAnalysisDetailDialog.tsx, PageImageViewer.tsx}

scripts/
├── common/d1.py                               # TABLE_ORDER + analysis_records flatten keys
├── scraper/runner.py                          # payload table keys + det-id seed + _document_id helper
├── scraper/extractors/documentos.py           # RETAINED (portal "documento" downloader)
└── analysis/
    ├── documentos.py → attachments.py         # builder module renamed; symbols renamed
    ├── extractions.py, loader.py, models.py, images.py, nf_groups.py, verdicts.py, __main__.py
    └── checks/{advanced.py, consistency.py}

drizzle/<new>.sql                              # generated: drop + recreate renamed tables
docs/{schema-migration-map.md, ...}            # documento→attachments mapping updated
CLAUDE.md, README.md, scripts/README.md        # terminology updated
.claude/agents/{analyze-docs,review-mismatch,fix-mismatch}.md  # identifier references updated
.claude/skills/{classify-period,classify-doc-page,improve-classification}/SKILL.md
```

**Structure Decision**: Existing web + Python-CLI layout is preserved; only names change. Directory renames: `src/app/api/document-analyses/` → `src/app/api/attachment-analyses/`; `scripts/analysis/documentos.py` → `scripts/analysis/attachments.py`; component file `DocumentAnalysisDetailDialog.tsx` → `AttachmentAnalysisDetailDialog.tsx`.

## Complexity Tracking

No constitution violations — section intentionally empty.
