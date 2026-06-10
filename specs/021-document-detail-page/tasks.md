# Tasks: Dedicated Document Detail Page

**Feature**: `021-document-detail-page` | **Spec**: [spec.md](./spec.md) | **Plan**: [plan.md](./plan.md)

**Tests**: No automated tests (Constitution III — no framework configured; none requested). Verification
is manual via `quickstart.md`.

**Organization**: Tasks are grouped by user story. US1 (P1) is the MVP — a usable detail page on its
own. US2 (P2) adds related documents. US3 (P3) preserves the per-entry deep link.

## Path conventions

Single Next.js app; paths are repo-relative under `src/`.

---

## Phase 1: Setup

- [x] T001 Confirm local data prerequisites for verification: a built document with linked entries
  exists in local D1 (run the scrape + `build-documents` flow if needed), ideally one whose entries
  are also linked to another document and whose source attachment has page images — recorded in
  `specs/021-document-detail-page/quickstart.md`. No code change.

---

## Phase 2: Foundational (blocking prerequisites)

**Purpose**: Extend the data endpoint that every user story reads. This is the single blocking task
before any UI work.

- [x] T002 Extend `GET /api/documents/[id]` in `src/app/api/documents/[id]/route.ts` to return the full
  detail view model per `contracts/document-detail.md`:
  - Keep the existing role check (admin/member → else 403) and 404 when the document row is absent.
  - Enrich each linked entry with `category`, `subcategory`, `vendor`, `unitCode` by joining
    `subcategories`→`categories`, `vendors` (LEFT), `units` (LEFT) — mirror the joins in
    `src/app/api/entries/route.ts`. Keep `entryId, period, date, description, amount,
    sourceAttachmentId`; order by `period`, then `date`.
  - Add `imageSources[]`: distinct `document_entries.source_attachment_id` for this document,
    inner-joined to `attachment_analyses` (so only attachments with an analysis appear), each as
    `{ attachmentId, analysisId, entryId, period }`, deduped by `analysisId`.
  - Add `relatedDocuments[]`: other `documents` sharing ≥1 entry with this document (self excluded),
    each with `id, documentNumber, issuerCnpj, issuerName, documentType, totalValue`, plus `sumEntries`
    (live sum over that related document's OWN links) and `status` via `documentStatus()` from
    `@/lib/documents`; order by `issuerName`, then `documentNumber`.
  - Keep `sumEntries`/`status` for the subject document as today (reuse `documentStatus`).

**Checkpoint**: The endpoint returns the documented shape — verifiable with a `curl`/browser request to
`/api/documents/<id>` while signed in.

---

## Phase 3: User Story 1 — View a document's full detail on one page (Priority: P1) 🎯 MVP

**Goal**: Clicking a document row navigates to `/dashboard/documents/[id]`, a page showing the header,
page image(s), and all linked entries with their details.

**Independent Test**: From the list, click a document with ≥1 linked entry; confirm a detail page (not
a dialog) shows the header, ≥1 page image (when one exists), and every linked entry with its details —
no further navigation.

- [x] T003 [US1] Create the route `src/app/dashboard/documents/[id]/page.tsx`: a thin server component
  that reads the route `id` param and renders `<DocumentDetailClient documentId={id} />`. It sits under
  the existing auth-gated `/dashboard` layout (no extra auth code needed).
- [x] T004 [US1] Create `src/app/dashboard/documents/[id]/DocumentDetailClient.tsx` (client component):
  fetch `/api/documents/${documentId}`; render loading, error, and a "not found" state (on 404, FR-010);
  render the **document header** card — number, issuer name + CNPJ, type, total, sum of linked entries,
  and the status badge (reuse the `StatusBadge` pattern from `DocumentsClient.tsx`; extract a shared
  `StatusBadge` if convenient). Include a back link to `/dashboard/documents`. Currency formatting
  mirrors `DocumentsClient` (`pt-BR`/BRL).
- [x] T005 [US1] In `DocumentDetailClient.tsx`, render the **linked entries** section: a table/list of
  all `entries[]` showing period, date, description, live amount, category, subcategory, vendor, unit.
  Empty state when there are no linked entries (FR-004 edge).
- [x] T006 [US1] In `DocumentDetailClient.tsx`, render the **document image(s)** section: for each
  `imageSources[]` item, fetch `/api/attachment-analyses/${analysisId}/pages` and render each page via
  the existing `PageImageViewer` (import from `src/app/dashboard/entries/PageImageViewer.tsx`; if a
  cross-segment import reads awkwardly, promote it to `src/components/PageImageViewer.tsx` and update
  the existing entries import). Attribute multi-source documents by the contributing entry/period.
  A pages-list/image failure or empty list is non-fatal and must not block header/entries (FR-009);
  show a graceful "no image" state when there are no sources/pages.
- [x] T007 [US1] Edit `src/app/dashboard/documents/DocumentsClient.tsx`: make each document row navigate
  to `/dashboard/documents/${row.id}` (via `next/link` or `useRouter().push`) instead of calling
  `openDetail`; remove the detail `Dialog` and its `detail`/`detailLoading`/`openDetail` state and the
  now-unused imports (`Dialog*`, the `DocumentDetail`/`LinkedEntry` types, `entryHref`). Keep the list
  filters, search, virtualized table, and `StatusBadge`.

**Checkpoint**: US1 fully functional and independently testable (quickstart steps 1–5, 8–11).

---

## Phase 4: User Story 2 — Reach related documents from the same page (Priority: P2)

**Goal**: The detail page lists the other real documents linked to the same entries, each navigable to
its own detail page.

**Independent Test**: Open a document whose linked entries are also linked to ≥1 other document; confirm
those (and only those — current document and attachments excluded) are listed and each navigates to its
own detail page.

- [x] T008 [US2] In `DocumentDetailClient.tsx`, render the **related documents** section from
  `relatedDocuments[]`: each row shows number, issuer, type, total, and status badge, and links to
  `/dashboard/documents/${related.id}`. Empty state when the array is empty (FR-006 edge); the subject
  document never appears (already excluded server-side).

**Checkpoint**: US2 functional (quickstart step 6). Navigating between related documents works because
each target reuses the same page/route.

---

## Phase 5: User Story 3 — Drill into a specific linked entry (Priority: P3)

**Goal**: Preserve the per-entry deep link into the entries view.

**Independent Test**: From a linked entry on the detail page, activate its "open in entries" affordance;
confirm it lands on `/dashboard/entries?period=…&entry=…` focused on that entry.

- [x] T009 [US3] In `DocumentDetailClient.tsx`, add per-entry deep link to
  `/dashboard/entries?period=${period}&entry=${entryId}` (reuse the `entryHref` shape removed from
  `DocumentsClient`), rendered alongside each entry row (e.g. an "Open" link like the old dialog).

**Checkpoint**: US3 functional (quickstart step 7); no entries-view change required (it already reads
those params).

---

## Phase 6: Polish & Cross-Cutting

- [x] T010 Run `pnpm lint` and `pnpm format`; fix any issues. Confirm no `any` without justification and
  no unused imports left in `DocumentsClient.tsx` (Constitution I, III).
- [x] T011 Manual verification per `specs/021-document-detail-page/quickstart.md` (use the `ui-login` /
  `verify` skill): all US acceptance scenarios + edge cases (not-found, no-image, zero-links, shareable
  URL).

---

## Dependencies & Execution Order

- **Setup (T001)** → **Foundational (T002)** must complete before any UI story.
- **US1 (T003–T007)** depends on T002. T003→T004 ordered (page renders the client). T005, T006 edit the
  same file as T004 — do sequentially (no `[P]`). T007 edits a different file and can proceed once the
  route exists (after T003).
- **US2 (T008)** depends on T002 (data) + T004 (the client shell). Independent of US1's image/entry work.
- **US3 (T009)** depends on T004/T005 (entry rows exist).
- **Polish (T010–T011)** last.

```text
T001 → T002 → ┬─ T003 → T004 → T005 → T009
              │            └─ T006
              │            └─ T008
              └─ (T007 after T003)
                                         → T010 → T011
```

## Parallel Opportunities

- T002 (API) and T001 (data prep) are independent and can overlap.
- After T004, the three section tasks T005 (entries), T006 (images), T008 (related docs) touch the
  same file (`DocumentDetailClient.tsx`); treat as sequential, not parallel, to avoid edit conflicts.
- T007 (edit `DocumentsClient.tsx`) is a different file and can run in parallel with the
  `DocumentDetailClient` work once T003 exists — marked separately since it touches no other task's file.

## Implementation Strategy

- **MVP = Phase 1 + 2 + US1 (T001–T007)**: a shareable detail page with header, images, and all linked
  entries — the core ask (a 10-entry document inspected in one navigation).
- Then layer US2 (related docs) and US3 (entry deep link), each an independent increment.
- Finish with lint/format + manual verification.
