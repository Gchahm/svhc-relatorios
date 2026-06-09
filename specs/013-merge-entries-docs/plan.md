# Implementation Plan: Merge Document Analyses into the Entries page

**Branch**: `013-merge-entries-docs` | **Date**: 2026-06-09 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/013-merge-entries-docs/spec.md`

## Summary

Fold the standalone Document Analyses page into the period-scoped Entries page. Each entry that has an analysed fiscal document shows inline amount/vendor/date match badges plus a document-type indicator and becomes clickable to open the existing detail dialog (extracted fields + page images). Two new filters (document type, document match status) and a period-level document-health summary are added next to the existing entry filters. The old `/dashboard/document-analyses` route redirects to `/dashboard/entries` and its separate "Docs" nav item is removed.

Technical approach: add an optional `?period=` filter to the existing `GET /api/document-analyses` endpoint so the analyses can be scoped to the selected period; in `EntriesClient`, fetch entries and (period-scoped) analyses together, build a `Map<entryId, DocAnalysisRow>` (latest analysis per entry), and render the inline badges + click-to-detail. Reuse the existing `DocumentAnalysisDetailDialog` / `PageImageViewer` (relocated under `entries/`). No schema change; read-only over existing D1 data.

## Technical Context

**Language/Version**: TypeScript 5 / React 19 / Next.js 15 (App Router)  
**Primary Dependencies**: Drizzle ORM (D1), better-auth, shadcn/ui (card, badge, dialog, select, input, multi-select), lucide-react, @tanstack/react-virtual — **no new npm dependencies**  
**Storage**: Cloudflare D1 (SQLite) — tables `entries`, `document_analyses`, `documents`, `document_analysis_records`, `accountability_reports`, `vendors`, `subcategories`, `categories`, `units` — all **read-only** here  
**Testing**: None configured (repo has no test framework; per Constitution III tests are OPTIONAL and not requested by this spec). Validation is manual + `pnpm lint`/`pnpm format`.  
**Target Platform**: Cloudflare Workers via `@opennextjs/cloudflare`  
**Project Type**: Web application (Next.js App Router, single app)  
**Performance Goals**: Merged list stays smoothly scrollable for the largest existing period (preserve the existing `@tanstack/react-virtual` virtualization; no perceptible regression vs. today's Entries page)  
**Constraints**: Period-scoped (follows the entry list); presentation/navigation change only — no data mutation, no re-analysis, no schema migration  
**Scale/Scope**: Hundreds of entries per period; a subset have analysed documents. One merged page, one redirect, one nav edit, one API query-param addition.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- **I. Type Safety & Schema Discipline** — PASS. No schema change (no `db:generate`/migration). New code is fully typed; the `DocAnalysisRow` type is reused; no `any`.
- **II. Cloudflare-Native Architecture** — PASS. The API change reuses `await getDb()`; no new bindings; the period filter is a standard Drizzle `where`. No build-time/runtime binding assumptions added.
- **III. Quality Gates Before Commit** — PASS. `pnpm lint` + `pnpm format` will run before commit. No tests mandated (none requested; none exist).
- **IV. Security & Auth by Default** — PASS. The reused/extended endpoints keep the existing `ALLOWED_ROLES` session gate; the redirect lands inside the already auth-gated `/dashboard` layout. No public exposure added.
- **V. Simplicity & Incremental Delivery** — PASS. Reuses the existing dialog, endpoints, virtualized list, and shadcn components; adds one optional query param rather than a new endpoint. Delivered as priority-ordered slices (P1 surfacing+detail, P2 filters+summary, P3 redirect+nav cleanup).

No violations — Complexity Tracking left empty.

## Project Structure

### Documentation (this feature)

```text
specs/013-merge-entries-docs/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output (view-model shapes; no DB schema change)
├── quickstart.md        # Phase 1 output (manual verification)
├── contracts/           # Phase 1 output (the extended API contract)
│   └── document-analyses.md
└── tasks.md             # Phase 2 output (speckit tasks)
```

### Source Code (repository root)

```text
src/
├── app/
│   ├── api/
│   │   └── document-analyses/
│   │       └── route.ts                 # EDIT: accept optional ?period= filter
│   └── dashboard/
│       ├── layout.tsx                   # EDIT: remove "Docs" nav link (+ unused FileSearch import)
│       ├── entries/
│       │   ├── page.tsx                 # unchanged (renders EntriesClient)
│       │   ├── EntriesClient.tsx        # EDIT: fetch analyses, join by entryId, badges,
│       │   │                            #       doc filters, doc-health summary, click-to-detail
│       │   ├── DocumentAnalysisDetailDialog.tsx  # MOVED here from document-analyses/
│       │   └── PageImageViewer.tsx               # MOVED here from document-analyses/
│       └── document-analyses/
│           └── page.tsx                 # REPLACE: server redirect to /dashboard/entries
│                                        # (DocumentAnalysesClient.tsx deleted; dialog/viewer moved out)
```

**Structure Decision**: Single Next.js App Router app (matches the existing repo). The Entries page becomes the merged home; the shared detail components move into `entries/` so the `document-analyses/` folder collapses to a redirect. The `DocAnalysisRow` type (currently exported from `DocumentAnalysesClient.tsx`) is redefined/exported from `EntriesClient.tsx`, which the dialog imports.

## Complexity Tracking

> No Constitution violations — nothing to justify.
