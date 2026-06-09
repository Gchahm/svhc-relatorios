# Phase 1 Data Model: View Document Page Images from Object Storage

**No D1 schema change.** This feature adds an object store and derives all linkage from existing
persisted data. This document defines the *logical* entities and the deterministic key mapping.

## Existing data reused (no changes)

### `documents` (D1, unchanged)
- `id` (uuid, PK)
- `entry_id` (uuid, unique → `entries.id`)
- `external_document_id` (int)
- **`file_path`** (text, nullable) — `;`-separated list of page-image paths, e.g.
  `../data/scrape/2025-12/<entry_id>_p1.jpg;../data/scrape/2025-12/<entry_id>_p2.png`.
  **This is the authoritative source of a document's pages.**

### `document_analyses` (D1, unchanged)
- `id` (uuid, PK) — what the UI/API key off.
- `document_id` (uuid, unique → `documents.id`) — join to reach `file_path`.

### `document_analysis_records` (D1, unchanged)
- `page_index` (int, 0-based), `page_label` (text, e.g. `p3`), `artifact_role`, `response`, … —
  the extracted fields shown today, matched to images by `page_label` / `page_index`.

## New logical entity: Document Page Image (stored in R2, not D1)

Represents one page image object in the `fiscal-documents` bucket.

| Attribute | Source | Notes |
|-----------|--------|-------|
| `objectKey` | derived from `file_path` segment | `<period>/<basename>` — the R2 key (see mapping) |
| `pageLabel` | parsed from basename `_p<N>` | e.g. `p1`; used to match the extracted record |
| `pageIndex` | `<N> - 1` | 0-based, aligns with `document_analysis_records.page_index` |
| `ext` | basename extension | `jpg` / `jpeg` / `png` → content type |
| `bytes` | R2 object body | streamed by the image route; absent ⇒ "unavailable" |

This entity is **not persisted in D1**; it is computed on demand from `file_path` and read from R2.

## Deterministic key mapping (single source of truth for read & write)

Both `scripts/upload-images-to-r2.mjs` (write) and the image route (read) MUST use the identical
normalization so keys agree:

```
filePathSegment  = one entry of documents.file_path split on ";"   // "../data/scrape/2025-12/<id>_p2.png"
normalized       = filePathSegment.replace(/^(\.\.\/)+/, "")        // strip leading "../"
afterScrapeRoot  = normalized.split("data/scrape/").pop()           // "2025-12/<id>_p2.png"
objectKey        = afterScrapeRoot                                  // R2 key, e.g. "2025-12/<id>_p2.png"
basename         = objectKey.split("/").pop()                       // "<id>_p2.png"
pageLabel        = basename.match(/_p(\d+)\.[^.]+$/)?.[1] → "p" + N // "p2"
ext              = basename.split(".").pop().toLowerCase()          // "png"
```

### Page ordering
Pages are ordered by `pageIndex` ascending (i.e. the order they appear in `file_path`), matching the
existing per-page record ordering in `/api/document-analyses/[id]`.

### Content-type derivation
| ext | Content-Type |
|-----|--------------|
| `jpg`, `jpeg` | `image/jpeg` |
| `png` | `image/png` |
| other | `application/octet-stream` (UI treats as unavailable / non-displayable) |

## Validation & integrity rules

- **Ownership**: the image route MUST only serve a page that belongs to the requested
  `document_analyses.id` (resolve via `file_path`); a `[page]` not present in that document's
  `file_path` → 404 (never serve an arbitrary key).
- **Missing object**: `bucket.get(objectKey) === null` → 404 → UI placeholder (FR-006). Not an error.
- **Null `file_path`**: document with no pages → empty page list → no image area (Edge Case).
- **Idempotency**: object key is a pure function of `file_path`; re-uploading overwrites the same key
  (FR-010), never duplicates.
