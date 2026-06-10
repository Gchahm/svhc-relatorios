# Implementation Plan: Dedicated Document Detail Page

**Branch**: `021-document-detail-page` | **Date**: 2026-06-10 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/021-document-detail-page/spec.md`

## Summary

Replace the in-list document dialog on `/dashboard/documents` with a dedicated, shareable detail page
at `/dashboard/documents/[id]`. The page shows the document's identity + reconciliation header, its
page image(s) sourced from the linked entries' provenance attachments, the full list of linked entries
with each entry's details (period, date, description, live amount, category, subcategory, vendor,
unit), and the *other* real documents linked to the same entries (each navigable to its own detail
page). Implemented by extending the existing `GET /api/documents/[id]` to return entry details +
image sources + related documents, adding one App Router page, and turning list rows into navigations.
No schema change; reuses the existing authenticated attachment page-image routes and `PageImageViewer`.

## Technical Context

**Language/Version**: TypeScript 5 / React 19 / Next.js 15 (App Router)
**Primary Dependencies**: Drizzle ORM (Cloudflare D1), better-auth, shadcn/ui (card, badge, button,
table-as-divs), lucide-react. Page images via the existing R2 (`DOCUMENTS`) streaming routes. **No new
npm dependencies.**
**Storage**: Cloudflare D1 (SQLite). Tables read: `documents`, `document_entries`, `entries`,
`accountability_reports`, `categories`, `subcategories`, `vendors`, `units`, `attachments`,
`attachment_analyses`. All **read-only** — no migration.
**Testing**: No test framework configured (Constitution III) — manual verification via `ui-login` /
`verify` skill against the running dashboard.
**Target Platform**: Cloudflare Workers via `@opennextjs/cloudflare`.
**Project Type**: Web application (single Next.js app).
**Performance Goals**: Detail page renders in one API round trip for the document + entries + related
docs; images load lazily/independently per source. No regression vs. the current dialog.
**Constraints**: Auth-gated to roles `admin`/`member` (Constitution IV); image keys resolved
server-side, never client-supplied. A page-image failure must not block the rest of the page.
**Scale/Scope**: Hundreds of documents; a document links to a handful up to ~dozens of entries.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- **I. Type Safety & Schema Discipline**: PASS. Pure TypeScript; no schema change (all relationships
  already exist). No `any` introduced. No auth-schema change.
- **II. Cloudflare-Native Architecture**: PASS. All DB access via `await getDb()`; page images reuse
  the existing `getDocumentsBucket()`-backed routes. No direct connections, no new bindings.
- **III. Quality Gates Before Commit**: PASS. `pnpm lint` + `pnpm format` before commit. Tests
  OPTIONAL and not requested; manual UI verification will accompany the change.
- **IV. Security & Auth by Default**: PASS. New page is under the auth-gated `/dashboard` layout; the
  extended API keeps the existing role check; image object keys remain resolved server-side from
  `file_path` (client supplies only the attachment-analysis id + page label, both validated).
- **V. Simplicity & Incremental Delivery**: PASS. Extends one existing endpoint, adds one page, reuses
  `PageImageViewer`, `documentStatus`, the existing image/pages routes, and shadcn primitives. No new
  abstraction or dependency. Delivered as prioritized, independently shippable slices (P1 page → P2
  related docs → P3 entry deep links).

**No violations — Complexity Tracking left empty.**

## Project Structure

### Documentation (this feature)

```text
specs/021-document-detail-page/
├── plan.md              # This file
├── spec.md              # Feature spec
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output (read-only view model — no schema change)
├── quickstart.md        # Phase 1 output (manual verification)
├── contracts/
│   └── document-detail.md   # GET /api/documents/[id] response contract (extended)
└── checklists/
    └── requirements.md  # Spec quality checklist (from specify)
```

### Source Code (repository root)

```text
src/
├── app/
│   ├── api/
│   │   └── documents/
│   │       └── [id]/route.ts          # EXTEND: add entry details, image sources, related docs
│   └── dashboard/
│       ├── documents/
│       │   ├── page.tsx               # unchanged (lists documents)
│       │   ├── DocumentsClient.tsx    # EDIT: row click navigates to detail page; remove dialog
│       │   └── [id]/
│       │       ├── page.tsx           # NEW: server page → renders DocumentDetailClient
│       │       └── DocumentDetailClient.tsx  # NEW: header + images + entries + related docs
│       └── entries/
│           └── PageImageViewer.tsx    # REUSE (import; optionally promote to a shared location)
└── lib/
    └── documents.ts                   # REUSE documentStatus()
```

**Structure Decision**: Single Next.js App Router app (Option 2 "web" collapsed to one project, as the
repo already is). The detail page is a nested dynamic route under the existing `documents` segment so
it inherits the `/dashboard` auth layout. The data layer is the existing `GET /api/documents/[id]`,
extended in place rather than split into sub-resources (Principle V — one round trip, one endpoint).
Page images reuse the existing `GET /api/attachment-analyses/[analysisId]/pages` + `/image/[page]`
routes unchanged; the detail API only needs to hand the client the right attachment-analysis ids.

## Complexity Tracking

> No Constitution violations — section intentionally empty.
