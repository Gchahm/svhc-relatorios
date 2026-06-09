---
description: "Task list for feature 012-r2-document-images"
---

# Tasks: View Document Page Images from Object Storage

**Input**: Design documents from `/specs/012-r2-document-images/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/

**Tests**: None. The spec requested no tests and the repo has no test framework (Constitution III);
verification is manual via `quickstart.md`.

**Organization**: Tasks grouped by user story. US1 (inline view) is the MVP; US2 (enlarge) builds on it.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependency on an incomplete task)
- **[Story]**: US1 / US2 (Setup, Foundational, Polish have no story label)

## Path Conventions

Single Next.js web app — paths are repo-root-relative under `src/`, `scripts/`, and project root.

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Declare the R2 bucket binding and its type so the app and tooling can reach it.

- [X] T001 [P] Add the R2 bucket binding to `wrangler.toml`: a `[[r2_buckets]]` block with
  `binding = "DOCUMENTS"` and `bucket_name = "fiscal-documents"` (place it after the `[[kv_namespaces]]` block).
- [X] T002 [P] Add `DOCUMENTS: R2Bucket;` to the `CloudflareEnv` interface in `env.d.ts` and import
  `R2Bucket` from `@cloudflare/workers-types` (alongside the existing `D1Database, KVNamespace` import).

**Checkpoint**: The `DOCUMENTS` binding exists and is typed; `getCloudflareContext().env.DOCUMENTS` type-checks.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: The R2 access seam and the populated bucket — both user stories are meaningless without
images in storage and a helper to reach them.

**⚠️ CRITICAL**: No user-story work can begin until this phase is complete.

- [X] T003 Create `src/lib/r2.ts` exporting: (a) `getDocumentsBucket()` — returns
  `(await getCloudflareContext({ async: true })).env.DOCUMENTS`, mirroring `getDb()` in `src/db/index.ts`;
  (b) `objectKeyFromFilePath(segment: string): string` — strips leading `../` and everything up to and
  including `data/scrape/`, returning `<period>/<basename>`; (c) `parsePage(segment)` returning
  `{ pageLabel, pageIndex, ext }` from the basename `_p<N>.<ext>`. Implement the exact normalization in
  `data-model.md` (single source of truth). Depends on T002.
- [X] T004 [P] Create `scripts/upload-images-to-r2.mjs` — an idempotent Node ESM uploader modeled on
  `scripts/import-to-d1.mjs`: `parseArgs` for `--input` (default `data/scrape`), `--period`, `--remote`
  (default local), `--dry-run`; walk the period folder(s) for `*_p*.{jpg,jpeg,png}`, compute the R2 key
  with the **same** normalization as `data-model.md` (replicate the small function, with a comment
  cross-referencing `src/lib/r2.ts` / data-model.md), and run `wrangler r2 object put
  fiscal-documents/<key> --file <path>` (append `--local` unless `--remote`); print a per-file/summary log.
- [X] T005 Populate local R2: run `node scripts/upload-images-to-r2.mjs --period 2025-12` (or all
  periods) and confirm objects exist via `wrangler r2 object get fiscal-documents/<key> --local`.
  Depends on T001, T004.

**Checkpoint**: `getDocumentsBucket()` is importable and the local bucket holds the period's page images.

---

## Phase 3: User Story 1 - View a document's page images inline (Priority: P1) 🎯 MVP

**Goal**: In the document-analysis detail dialog, show each page's image in order next to its extracted
fields, auth-gated, with a graceful placeholder for missing images and non-blocking load.

**Independent Test**: Open a document with `file_path` set → page images render in order beside the
per-page records; a document with a missing object shows a placeholder while the rest renders; an
unauthenticated `GET …/image/p1` returns 403.

- [X] T006 [P] [US1] Create `src/app/api/document-analyses/[id]/pages/route.ts` — `GET` returning the
  ordered page list per `contracts/pages-list.md`: reuse the `initAuth()` + role-check from
  `src/app/api/document-analyses/[id]/route.ts` (403 on failure), join `document_analyses → documents`
  to read `file_path`, split on `;`, map each segment via `parsePage` to
  `{ pageIndex, pageLabel, ext, imageUrl: "/api/document-analyses/<id>/image/<pageLabel>" }`, sorted by
  `pageIndex`; `[]` when `file_path` is null; 404 when the analysis id is unknown. Depends on T003.
- [X] T007 [P] [US1] Create `src/app/api/document-analyses/[id]/image/[page]/route.ts` — `GET`
  streaming one page per `contracts/page-image.md`: auth/role check (403), look up `file_path` for the
  id, find the segment whose `pageLabel` matches `[page]` (else 404 — never build an arbitrary key),
  `objectKeyFromFilePath` → `getDocumentsBucket().get(key)` (null → 404), stream `obj.body` with
  `Content-Type` from `ext` (`image/jpeg`/`image/png`) and `Cache-Control: private, max-age=3600`.
  Depends on T003.
- [X] T008 [P] [US1] Create `src/app/dashboard/document-analyses/PageImageViewer.tsx` — a client
  component rendering `<img loading="lazy">` from a passed `imageUrl`, with a loading skeleton and an
  `onError` → "image unavailable" placeholder (FR-006/FR-007). (Lightbox is added in US2 — keep the
  inline render self-contained for now.)
- [X] T009 [US1] Integrate images into `src/app/dashboard/document-analyses/DocumentAnalysisDetailDialog.tsx`:
  add a second effect fetching `/api/document-analyses/<id>/pages`, render a `PageImageViewer` per page
  (ordered), and associate each image with its matching per-page record by `pageLabel`/`pageIndex`
  (show the image even when no record matches; keep extracted fields rendering regardless of image
  state). Depends on T006, T007, T008.

**Checkpoint**: US1 is fully functional and independently testable (the MVP).

---

## Phase 4: User Story 2 - Inspect a page image closely (Priority: P2)

**Goal**: Click a page image to view it at full resolution; dismissing returns to the detail in place.

**Independent Test**: With an image displayed, click it → it opens enlarged/full-resolution in an
overlay; dismiss → back to the detail with scroll/position preserved.

- [X] T010 [US2] Add a click-to-enlarge lightbox to
  `src/app/dashboard/document-analyses/PageImageViewer.tsx` using the existing shadcn `Dialog`
  (`@/components/ui/dialog`): clicking the inline image opens a max-size dialog showing the full-resolution
  image; dialog close returns to the detail. No new dependency. Depends on T008 (same file) and T009.

**Checkpoint**: US1 and US2 both work; auditors can view inline and enlarge.

---

## Phase 5: Polish & Cross-Cutting Concerns

- [X] T011 [P] Add a short "Document images (R2)" note to `CLAUDE.md` Important Patterns: the
  `DOCUMENTS` binding, the `<period>/<basename>` key scheme, `getDocumentsBucket()`, and that new
  periods must be uploaded via `scripts/upload-images-to-r2.mjs` (`--remote` for prod).
- [X] T012 Run `pnpm lint` and `pnpm format`; fix any findings.
- [X] T013 Run the `quickstart.md` verification end-to-end (US1 inline, US2 enlarge, missing-image
  placeholder, and the unauthenticated 403 check).

---

## Dependencies & Execution Order

### Phase Dependencies
- **Setup (Phase 1)**: no dependencies — start immediately.
- **Foundational (Phase 2)**: depends on Setup — BLOCKS both user stories.
- **US1 (Phase 3)**: depends on Foundational.
- **US2 (Phase 4)**: depends on US1 (it enhances the same `PageImageViewer` + dialog).
- **Polish (Phase 5)**: after the desired stories are complete.

### Within / across stories
- T003 (r2 helper) blocks both API routes (T006, T007).
- T006, T007, T008 are different files → parallelizable; T009 needs all three.
- T010 edits the same file as T008 → sequential after T009.

### Parallel Opportunities
- T001, T002 (Setup) in parallel.
- T004 can be written in parallel with T003 (it replicates the key logic, doesn't import it).
- T006, T007, T008 (US1) in parallel, then T009.

---

## Parallel Example: User Story 1

```bash
# After Foundational (T003–T005), launch US1 building blocks together:
Task: "Create src/app/api/document-analyses/[id]/pages/route.ts"          # T006
Task: "Create src/app/api/document-analyses/[id]/image/[page]/route.ts"   # T007
Task: "Create src/app/dashboard/document-analyses/PageImageViewer.tsx"    # T008
# Then integrate:
Task: "Wire page images into DocumentAnalysisDetailDialog.tsx"            # T009
```

---

## Implementation Strategy

### MVP First (US1 only)
1. Phase 1 Setup → 2. Phase 2 Foundational → 3. Phase 3 US1 → **STOP & validate** (inline images,
   placeholder, 403) → demo. This is a complete, shippable increment.

### Incremental Delivery
- Setup + Foundational → bucket bound & populated.
- + US1 → inline image viewing (MVP).
- + US2 → full-resolution enlarge.
- Polish → docs, lint/format, quickstart sign-off.

---

## Notes
- No D1 migration and no new npm dependencies (per plan.md).
- The R2 key normalization lives canonically in `data-model.md`; `src/lib/r2.ts` (TS, for the routes)
  and `scripts/upload-images-to-r2.mjs` (Node, for upload) MUST agree — keep them in sync.
- Client never sends a raw R2 key; the image route derives it from the document it owns (Constitution IV).
- Commit after each task or logical group; run lint/format before the PR.
