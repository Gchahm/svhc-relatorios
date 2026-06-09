# Implementation Plan: View Document Page Images from Object Storage

**Branch**: `012-r2-document-images` | **Date**: 2026-06-09 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/012-r2-document-images/spec.md`

## Summary

Add a Cloudflare R2 bucket (binding `DOCUMENTS`) to the project and surface each scraped fiscal
document's page image(s) inside the existing document-analysis detail dialog. Page images already
exist on disk under `data/scrape/<period>/<entry_id>_pN.<ext>` and their paths are already persisted
in `documents.file_path` (a `;`-separated list). A one-time, idempotent upload script pushes those
files into R2 keyed by `<period>/<basename>`; an auth-gated API route resolves the requested page to
its R2 object key **server-side** (from `file_path`, so the client never sends a raw key) and streams
the bytes; the detail dialog renders the images lazily next to the per-page extracted fields, with a
graceful "image unavailable" placeholder and a click-to-enlarge lightbox. No D1 schema change — the
document→image mapping is derived from the existing `file_path`.

## Technical Context

**Language/Version**: TypeScript 5 / React 19 / Next.js 15 (App Router); Node ESM (`.mjs`) for the upload script
**Primary Dependencies**: `@opennextjs/cloudflare` (R2 binding via `getCloudflareContext`), `@cloudflare/workers-types` (`R2Bucket` type), existing shadcn/ui `Dialog`, better-auth — **no new npm dependencies**
**Storage**: Cloudflare R2 bucket, binding `DOCUMENTS`, bucket name `fiscal-documents`; emulated locally by Miniflare (`.wrangler/state`) exactly as D1/KV are. Source images on disk under `data/scrape/<period>/`
**Testing**: None configured (per Constitution III); manual verification via `quickstart.md`
**Target Platform**: Cloudflare Workers (edge) via OpenNext + local dev (`pnpm preview` / `pnpm dev`)
**Project Type**: Web — single Next.js app (`src/`)
**Performance Goals**: Image route streams the R2 object (no buffering of the whole gallery); UI lazy-loads page images so extracted fields render immediately
**Constraints**: Edge runtime; all storage access via Cloudflare binding (no direct connections); image access auth-gated; **no DB migration**; upload script idempotent
**Scale/Scope**: Hundreds–low-thousands of page images per period; 1 detail dialog touched, 2 new API routes, 1 R2 helper, 1 upload script

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Notes |
|-----------|--------|-------|
| I. Type Safety & Schema Discipline | ✅ PASS | No D1 schema change (mapping derives from existing `documents.file_path`), so no migration. R2 binding is typed by adding `DOCUMENTS: R2Bucket` to `env.d.ts`'s `CloudflareEnv`. No `any`. |
| II. Cloudflare-Native Architecture | ✅ PASS | R2 reached only via `getCloudflareContext().env.DOCUMENTS` behind a `getDocumentsBucket()` helper (mirrors `getDb()`); binding declared in `wrangler.toml`. No hardcoded endpoints/credentials. |
| III. Quality Gates Before Commit | ✅ PASS | `pnpm lint` + `pnpm format` before commit. No tests mandated; manual verification in quickstart. |
| IV. Security & Auth by Default | ✅ PASS | Image route reuses the `initAuth()` + role-check pattern (`admin`/`member`) used by `/api/document-analyses`. Client never supplies an R2 key — the route derives it from the document it owns, preventing arbitrary-object reads. |
| V. Simplicity & Incremental Delivery | ✅ PASS | Reuses the existing shadcn `Dialog` for the lightbox and the existing detail dialog; upload script mirrors the existing `scripts/import-to-d1.mjs` (shell out to `wrangler`); P1 (inline view) ships independently of P2 (enlarge). |

**Result**: PASS — no violations. Complexity Tracking left empty.

## Project Structure

### Documentation (this feature)

```text
specs/012-r2-document-images/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/           # Phase 1 output
│   ├── pages-list.md    # GET /api/document-analyses/[id]/pages
│   └── page-image.md    # GET /api/document-analyses/[id]/image/[page]
└── checklists/
    └── requirements.md  # from specify
```

### Source Code (repository root)

```text
src/
├── lib/
│   └── r2.ts                                   # NEW: getDocumentsBucket() + objectKeyFromFilePath() helpers
├── app/
│   ├── api/
│   │   └── document-analyses/
│   │       └── [id]/
│   │           ├── route.ts                    # existing (per-page records) — unchanged
│   │           ├── pages/
│   │           │   └── route.ts                # NEW: ordered page list (label/index + image URL + key)
│   │           └── image/
│   │               └── [page]/
│   │                   └── route.ts            # NEW: stream one page image from R2 (auth-gated)
│   └── dashboard/
│       └── document-analyses/
│           ├── DocumentAnalysisDetailDialog.tsx # CHANGED: render page images + enlarge lightbox
│           └── PageImageViewer.tsx              # NEW: lazy image + loading/placeholder + lightbox (client)
└── db/
    └── fiscal.schema.ts                         # unchanged (documents.file_path already present)

scripts/
└── upload-images-to-r2.mjs                      # NEW: idempotent upload of data/scrape images → R2

wrangler.toml                                    # CHANGED: add [[r2_buckets]] binding DOCUMENTS
env.d.ts                                         # CHANGED: add DOCUMENTS: R2Bucket to CloudflareEnv
```

**Structure Decision**: Single Next.js web app — extends the established App Router conventions
under `src/app/api/` and the existing document-analyses dashboard feature (004). The R2 access helper
lives in `src/lib/r2.ts` (path alias `@/lib/r2`) to mirror the `@/db` seam; the upload tooling lives
under `scripts/` alongside `import-to-d1.mjs`.

## Complexity Tracking

> No Constitution violations — section intentionally empty.
