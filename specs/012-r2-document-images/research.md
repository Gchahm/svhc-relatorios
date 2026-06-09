# Phase 0 Research: View Document Page Images from Object Storage

The spec carried no `[NEEDS CLARIFICATION]` markers; this document records the design decisions that
resolve the open implementation choices, with rationale and rejected alternatives.

## D-1: Object-storage technology & binding

- **Decision**: Cloudflare R2, declared in `wrangler.toml` as `[[r2_buckets]]` with binding
  `DOCUMENTS` and bucket name `fiscal-documents`. Accessed at runtime only through
  `getCloudflareContext().env.DOCUMENTS`, wrapped in a `getDocumentsBucket()` helper in `src/lib/r2.ts`.
- **Rationale**: Constitution II mandates Cloudflare-native bindings; R2 is the project's native blob
  store and is emulated locally by Miniflare (the same engine behind the existing local D1/KV), so
  "same experience local and prod" (SC-005) comes for free. A helper mirrors the existing `getDb()`
  seam and keeps build-time vs. runtime separation.
- **Alternatives rejected**:
  - *KV for blobs* — KV is value-size limited and meant for small config, not page images.
  - *Serving from disk / public assets* — not durable at the edge, not available in prod Workers,
    and would bypass auth (Constitution IV).

## D-2: Object key scheme & document→image mapping

- **Decision**: Object key = the path **relative to `data/scrape/`**, i.e. `<period>/<basename>`,
  e.g. `2025-12/a1e29b40-..._p1.jpg`. Derived deterministically from the existing
  `documents.file_path` value by stripping any leading `../` and everything up to and including
  `data/scrape/`. The **same** normalization is used by both the upload script (write key) and the
  image route (read key), guaranteeing they agree. No new DB column.
- **Rationale**: FR-009 requires the mapping be derivable from data already stored. `file_path`
  already holds the full `;`-separated page list per document; normalizing it yields a stable, unique,
  collision-free key (the `entry_id` UUID + `_pN` suffix is globally unique). Avoiding a schema column
  honors Constitution I (no migration risk) and V (simplicity).
- **Alternatives rejected**:
  - *New `r2_key` column per page* — redundant with `file_path`; adds a migration and a sync burden.
  - *Content-hash keys* — the byte-identical-page grouping uses content hashes for NF dedup, but using
    a hash as the object key would lose the human-debuggable period/entry/page structure and require a
    new persisted lookup. The path-derived key is already unique.

## D-3: How the client requests an image (no raw keys over the wire)

- **Decision**: Two endpoints, both keyed by the **document-analysis id** the user already has:
  1. `GET /api/document-analyses/[id]/pages` → ordered list of `{ pageIndex, pageLabel, ext,
     available?, imageUrl }` derived from `documents.file_path`.
  2. `GET /api/document-analyses/[id]/image/[page]` → streams the bytes of one page from R2. The
     `[page]` segment is the page label (e.g. `p1`); the route looks up `file_path` for that analysis,
     finds the matching page, normalizes it to the R2 key **server-side**, and `get()`s it.
- **Rationale**: Constitution IV — the client never names an R2 object; it names a page of a document
  it is authorized to view, and the server resolves the key. This prevents enumeration/arbitrary-key
  reads. Keying both routes off the analysis id reuses the auth + lookup pattern already in
  `/api/document-analyses/[id]/route.ts`.
- **Alternatives rejected**:
  - *Signed R2 URLs to the browser* — more moving parts, harder to scope to the existing session, and
    leaks bucket structure; unnecessary for an auth-gated internal tool.
  - *One combined endpoint returning base64 images in JSON* — defeats lazy loading and streaming
    (FR-007), bloats payloads.

## D-4: Populating the bucket (idempotent upload)

- **Decision**: A standalone Node ESM script `scripts/upload-images-to-r2.mjs` that walks the period
  image files (default `data/scrape`, optional `--period <YYYY-MM>`) and uploads each via
  `wrangler r2 object put fiscal-documents/<key> --file <path>` — `--local` by default, `--remote`
  for production, plus `--dry-run`. Mirrors `scripts/import-to-d1.mjs` structure and flags.
- **Rationale**: R2 `put` is an upsert, so re-running overwrites the same key (FR-010 idempotency) and
  creates no duplicates. Shelling out to `wrangler` matches the existing import tooling (Constitution
  V) and needs no new dependency or Workers-runtime code path.
- **Alternatives rejected**:
  - *Fold upload into `import-to-d1.mjs`* — couples DB import to blob upload; keeping them separate
    lets each be re-run independently and keeps the import script focused. (Noted as a possible future
    convenience, not done now.)
  - *Upload from inside the app at request time* — would put large file I/O on the edge request path
    and require the disk files at runtime (unavailable in prod).
- **Known limitation**: one `wrangler` invocation per file is acceptable for hundreds–thousands of
  images but is not the fastest path; if volume grows, batch via the R2 S3-compatible API. Recorded in
  quickstart, not implemented now (YAGNI).

## D-5: Content type & missing-object handling

- **Decision**: The image route maps the file extension to a content type (`.jpg`/`.jpeg` →
  `image/jpeg`, `.png` → `image/png`) and sets `Content-Type` + a private `Cache-Control`
  (`private, max-age=...`). A missing object (`get()` returns null) yields HTTP **404**; the UI treats
  404 (and any non-OK) as "image unavailable" and shows a placeholder (FR-006) without blocking the
  rest of the detail (FR-007). Unauthorized → **403** (consistent with sibling routes).
- **Rationale**: Streaming with the right content type lets the browser render natively and lazily.
  404-as-placeholder keeps a stale/absent reference from breaking the view (Edge Cases).
- **Alternatives rejected**: *Throwing 500 on missing object* — turns an expected condition (image not
  yet uploaded) into an error and would break the detail view.

## D-6: Inline display + enlarge (US1 / US2)

- **Decision**: A new client component `PageImageViewer.tsx` renders an `<img loading="lazy">` with a
  loading skeleton and an `onError` → placeholder fallback; clicking it opens the existing shadcn
  `Dialog` as a full-resolution lightbox. The detail dialog fetches the page list alongside the
  per-page records and renders each image with its matching record (matched by `pageLabel`/`pageIndex`).
- **Rationale**: Reuses installed shadcn `Dialog` (Constitution V) — no new UI dependency. Native
  lazy-loading satisfies FR-007 without extra libraries. Matching by page label aligns images with the
  extracted fields already shown.
- **Alternatives rejected**:
  - *Add a lightbox library* — unnecessary; a `Dialog` with a large image covers SC-006.
  - *Render images server-side into the page* — breaks lazy/non-blocking loading and auth streaming.

## D-7: Local emulation parity (SC-005)

- **Decision**: No code branches on environment. Locally, `wrangler`/Miniflare fabricates the
  `fiscal-documents` bucket from the binding; `upload-images-to-r2.mjs --local` populates
  `.wrangler/state`. In prod the bucket is created once (`wrangler r2 bucket create fiscal-documents`)
  and populated with `--remote`. `pnpm clean` wipes local state (documented in quickstart).
- **Rationale**: Miniflare gives byte-for-byte the same `R2Bucket` API locally and in prod, so SC-005
  is satisfied with configuration/data differences only.
