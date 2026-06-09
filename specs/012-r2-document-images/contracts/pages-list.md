# Contract: List page images for a document analysis

`GET /api/document-analyses/[id]/pages`

Returns the ordered list of page images for one document analysis, derived from
`documents.file_path`. Used by the detail dialog to render the image gallery and to know which image
URL to load per page.

## Auth
- Same as `/api/document-analyses/[id]`: requires a better-auth session whose `user.role` ∈
  `{admin, member}`. Otherwise `403 { "error": "Unauthorized" }`.

## Path params
- `id` — `document_analyses.id`.

## Responses

### 200 OK
Ordered array (by `pageIndex` asc) of page descriptors:

```json
[
  {
    "pageIndex": 0,
    "pageLabel": "p1",
    "ext": "jpg",
    "imageUrl": "/api/document-analyses/<id>/image/p1"
  },
  {
    "pageIndex": 1,
    "pageLabel": "p2",
    "ext": "png",
    "imageUrl": "/api/document-analyses/<id>/image/p2"
  }
]
```

- `imageUrl` is the relative URL the client `<img>` loads (see `page-image.md`).
- Whether the underlying object actually exists is **not** probed here (avoids an R2 round-trip per
  page); the image route returns 404 and the UI shows the placeholder if it is missing.

### 200 OK — no pages
Document/analysis with `file_path = null` or empty → `[]`. UI renders no image area.

### 403 Forbidden
Unauthenticated / insufficient role.

### 404 Not Found
No `document_analyses` row with that `id` (or no joined `documents` row).

## Notes
- Derivation is pure string parsing of `file_path` (see `data-model.md`); no R2 access.
