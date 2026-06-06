# Implementation Plan: Surface per-page document-analysis detail in the UI

**Branch**: `004-doc-analysis-detail` | **Date**: 2026-06-06 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/004-doc-analysis-detail/spec.md`

## Summary

Expose the document-analysis data the pipeline already computes but never shows. Two reads are
added: (1) a new authenticated detail route `GET /api/document-analyses/[id]` that returns the
`document_analysis_records` rows for one analysis (currently queried by nothing), and (2) a
read-only detail view in `DocumentAnalysesClient` — a dialog opened from each list row — that
renders the roll-up fields already in the list payload (`issuerName`, `extractedCnpj`,
`documentNumber`, `serviceDescription`, `documentType`, `error`) plus the per-page records fetched
on demand from the new route. The detail view labels the well-known per-page amount fields
(gross / net / paid) and flags when the roll-up amount was reconciled against a payment artifact.
No schema, detection, or scraper changes.

## Technical Context

**Language/Version**: TypeScript 5 / React 19 / Next.js 15 (App Router)
**Primary Dependencies**: Drizzle ORM (D1), better-auth, shadcn/ui (dialog, badge, card), lucide-react, @tanstack/react-virtual (existing list)
**Storage**: Cloudflare D1 (SQLite) — tables `document_analyses`, `document_analysis_records` (read-only here)
**Testing**: None configured (per Constitution III); manual verification via running app
**Target Platform**: Cloudflare Workers via @opennextjs/cloudflare
**Project Type**: Web application (Next.js App Router; co-located API routes + client components under `src/app/`)
**Performance Goals**: Detail fetched on demand per opened analysis; list rendering unchanged (virtualized)
**Constraints**: DB access only via `await getDb()`; new route guarded by same `ALLOWED_ROLES` as list route; no Edge-incompatible APIs
**Scale/Scope**: One new GET route, one new detail-dialog component, minor edits to one existing client component. Per-analysis record count is small (pages of one document).

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- **I. Type Safety & Schema Discipline**: PASS. No schema change — reuses existing
  `documentAnalysisRecords` table. Per-page `response` is stored JSON; it is parsed into a typed
  shape with a safe fallback (raw text / parse error), no `any` without justification.
- **II. Cloudflare-Native Architecture**: PASS. New route uses `await getDb()`; no direct
  connections, no build-time binding assumptions.
- **III. Quality Gates Before Commit**: PASS. `pnpm lint` + `pnpm format` before commit. No tests
  mandated (none configured); manual verification of the detail view planned.
- **IV. Security & Auth by Default**: PASS. New route copies the exact session + `ALLOWED_ROLES`
  guard from the existing list route; returns 403 otherwise. Read-only.
- **V. Simplicity & Incremental Delivery**: PASS. Reuses existing shadcn `dialog`, `badge`, `card`,
  and `cn()`. No new dependencies. Roll-up detail (Story 1) ships independently of the per-page
  fetch (Story 2); reconciliation indicator (Story 3) is a small additive layer.

Post-Phase-1 re-check: PASS — design introduces no new dependencies, no schema change, no new
abstractions beyond one route handler and one presentational component. Complexity Tracking empty.

## Project Structure

### Documentation (this feature)

```text
specs/004-doc-analysis-detail/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/           # Phase 1 output
│   └── document-analysis-detail.md
├── checklists/
│   └── requirements.md  # from specify
└── tasks.md             # Phase 2 output (speckit tasks)
```

### Source Code (repository root)

```text
src/
├── app/
│   ├── api/
│   │   └── document-analyses/
│   │       ├── route.ts                 # EXISTING list route (unchanged)
│   │       └── [id]/
│   │           └── route.ts             # NEW: GET per-page records for one analysis
│   └── dashboard/
│       └── document-analyses/
│           ├── DocumentAnalysesClient.tsx   # EDIT: row click → open detail dialog
│           └── DocumentAnalysisDetailDialog.tsx  # NEW: detail dialog component
├── components/ui/
│   └── dialog.tsx                       # EXISTING shadcn dialog (reused)
└── db/
    └── fiscal.schema.ts                 # EXISTING (read-only reference; no change)
```

**Structure Decision**: Web application using Next.js App Router conventions already established in
`src/app/`. The new API route nests under the existing `document-analyses` route as a dynamic
`[id]` segment (mirroring the existing `api/alerts/[id]/route.ts` pattern). The detail UI is a new
presentational client component co-located with `DocumentAnalysesClient.tsx`, opened from a list
row; this keeps the virtualized list untouched and isolates the new view.

## Complexity Tracking

> No constitution violations. Section intentionally empty.
