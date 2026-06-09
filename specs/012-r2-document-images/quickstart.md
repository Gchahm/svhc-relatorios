# Quickstart: View Document Page Images from Object Storage

How to configure, populate, and verify the R2 document-image feature locally and in production.

## Prerequisites
- Page images present on disk under `data/scrape/<period>/` (produced by the scrape pipeline).
- D1 already imported (`documents.file_path` populated) so the detail dialog has documents to open.

## 1. Bucket binding (one-time config)

`wrangler.toml` gains:

```toml
[[r2_buckets]]
binding = "DOCUMENTS"
bucket_name = "fiscal-documents"
```

`env.d.ts` gains `DOCUMENTS: R2Bucket;` in the `CloudflareEnv` interface (typed via
`@cloudflare/workers-types`).

## 2. Populate R2

Local (Miniflare state under `.wrangler/state`):

```bash
node scripts/upload-images-to-r2.mjs            # all periods, --local by default
node scripts/upload-images-to-r2.mjs --period 2025-12
node scripts/upload-images-to-r2.mjs --dry-run  # list what would upload
```

Production (bucket must exist first):

```bash
wrangler r2 bucket create fiscal-documents       # once
node scripts/upload-images-to-r2.mjs --remote
```

The script is idempotent — re-running overwrites the same keys, no duplicates (FR-010).

> Note: the script invokes `wrangler r2 object put` once per file (mirrors `import-to-d1.mjs`). Fine
> for hundreds–thousands of images; batch via the S3-compatible API if volume grows.

## 3. Run the app

```bash
pnpm dev        # or: pnpm preview  (full Workers runtime, guaranteed bindings)
```

If a binding ever reads `undefined` under `pnpm dev`, use `pnpm preview`.

## 4. Verify (acceptance)

1. **US1 / SC-001, SC-002**: Open the dashboard → Document Analyses → click a document that has
   `file_path` set. Confirm each page renders as an image, in page order, beside its extracted fields.
2. **FR-006 / SC-003 (missing)**: Pick a document whose image you did *not* upload (or delete one key
   with `wrangler r2 object delete fiscal-documents/<key> --local`). Reopen — the page shows an
   "image unavailable" placeholder and the extracted fields still render.
3. **FR-007 (non-blocking)**: The extracted fields appear immediately; images fill in as they load.
4. **US2 / SC-006**: Click a page image → it opens enlarged/full-resolution; dismiss returns to the
   detail without losing position.
5. **FR-005 / SC-004 (auth)**: While logged out, request
   `GET /api/document-analyses/<id>/image/p1` directly → `403`. (E.g. `curl -i` without a session
   cookie.)

## 5. Housekeeping
- `pnpm clean` deletes `.wrangler` → wipes local R2 (and local D1). Re-run step 2 afterward.
- `pnpm lint` and `pnpm format` before committing (Constitution III).
