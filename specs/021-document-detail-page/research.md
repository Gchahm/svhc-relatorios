# Phase 0 Research: Dedicated Document Detail Page

The spec carried no `[NEEDS CLARIFICATION]` markers; this records the design decisions that resolve
the open implementation choices against the existing codebase.

## Decision 1 — Route shape: nested dynamic page under `documents`

- **Decision**: Add `/dashboard/documents/[id]` as a nested App Router segment
  (`src/app/dashboard/documents/[id]/page.tsx` + a `DocumentDetailClient`). Document rows in
  `DocumentsClient` become navigations to that URL; the existing detail `Dialog` is removed.
- **Rationale**: A nested segment inherits the existing `/dashboard` auth layout (Constitution IV)
  and yields a stable, shareable URL (FR-002, SC-005). It mirrors how the rest of the dashboard is
  organized (sibling list pages under `dashboard/*`). The document id is already the natural key the
  list passes today (`openDetail(row.id)`), so the change is a swap from `fetch` to navigation.
- **Alternatives considered**: (a) Keep the dialog and add a "view full page" link — rejected: the
  spec wants the page to *replace* the per-entry hopping, and two surfaces doubles maintenance.
  (b) A query-param modal route — rejected: less shareable/obvious than a real path.

## Decision 2 — Data: extend `GET /api/documents/[id]` in place

- **Decision**: Extend the existing single endpoint to return, in one payload: the document header
  (already present), `entries[]` enriched with `category`, `subcategory`, `vendor`, `unitCode`
  (joining `subcategories`→`categories`, `vendors`, `units` as the entries route does),
  `imageSources[]` (one per distinct provenance attachment that has an analysis), and
  `relatedDocuments[]` (other documents over the same entries, minus self, with their own
  total/sum/status).
- **Rationale**: One round trip for the whole page (Principle V, performance goal). The entry-detail
  joins already exist in `GET /api/entries`; reusing the same join shape keeps semantics consistent.
  The status math reuses `documentStatus()` from `src/lib/documents.ts` (FR-003, single tolerance).
- **Alternatives considered**: Separate sub-resource endpoints (`/entries`, `/related`, `/images`) —
  rejected as over-engineered for a read-only page; more endpoints, more auth boilerplate, more
  client fetch states for no benefit.

## Decision 3 — Document image sourcing: reuse the attachment page-image routes

- **Decision**: The detail API resolves each link's `document_entries.source_attachment_id` to its
  `attachment_analyses.id` (unique per attachment) and returns those as `imageSources[]` (with the
  contributing entry/period for attribution). The client renders each source's pages by calling the
  **existing** `GET /api/attachment-analyses/[analysisId]/pages` then `…/image/[page]` via the
  existing `PageImageViewer` component. Distinct source attachments are de-duplicated by analysis id.
- **Rationale**: Page images already live in R2 and are streamed only through the server-resolved
  key routes (Constitution IV — client never supplies a raw key). A "document" is a real doc found
  inside an attachment's pages, so the provenance attachment's page images *are* the document image.
  Reusing the routes means zero new R2 code and no new image endpoint (FR-005, FR-009).
- **Alternatives considered**: A new `/api/documents/[id]/image` route — rejected: would duplicate
  the key-resolution + streaming logic already in the attachment-analysis image route. Storing a
  per-document image — rejected: no such storage exists and the spec forbids new image processing.
- **Edge handling**: a source attachment with no analysis or no `file_path` simply contributes no
  pages; image-list/stream failures are swallowed client-side (as `AttachmentAnalysisDetailDialog`
  already does) so they never block the header/entries/related sections (FR-009).

## Decision 4 — Related documents query

- **Decision**: `relatedDocuments` = `SELECT DISTINCT d2` where a `document_entries` row for `d2`
  shares an `entry_id` with a `document_entries` row for the subject document, and `d2.id != subject`.
  Their `sumEntries`/`status` are computed over **each related document's own full link set** (not
  just the shared entries) so the badge matches what that document's own detail page would show.
- **Rationale**: Matches FR-006 ("other real documents linked to these entries"), excludes the
  subject (FR-006) and excludes attachments by construction (the query is over the `documents`
  entity, never `attachments`). Computing status over the doc's full links keeps the badge consistent
  with the list and the document's own page (no context-dependent status).
- **Alternatives considered**: Status over only the shared entries — rejected: would show a different
  badge for the same document depending on which page you came from, which is misleading.

## Decision 5 — Reuse vs. relocate `PageImageViewer`

- **Decision**: Import the existing `PageImageViewer` (currently in
  `src/app/dashboard/entries/PageImageViewer.tsx`). If a cross-segment import reads awkwardly, promote
  it to a shared location (e.g. `src/components/PageImageViewer.tsx`) and update the one existing
  import — a mechanical move, no behavior change.
- **Rationale**: The component already handles zoom/error states for the same R2-backed image URLs;
  rebuilding it would violate Principle V (reuse before new primitives).

## Resolved unknowns

All Technical Context fields are concrete; no remaining NEEDS CLARIFICATION.
