# Contract: Stream one page image

`GET /api/document-analyses/[id]/image/[page]`

Streams the bytes of a single page image from the R2 `DOCUMENTS` bucket. The route resolves the R2
object key **server-side** from the document's `file_path`; the client never supplies a raw key.

## Auth
- Same as the sibling routes: better-auth session with `user.role` ∈ `{admin, member}`, else
  `403 { "error": "Unauthorized" }`.

## Path params
- `id` — `document_analyses.id`.
- `page` — page label, e.g. `p1` (matches the basename `_p<N>` suffix).

## Behavior
1. Authenticate + authorize (403 on failure).
2. Look up `file_path` for `id` (join `document_analyses` → `documents`).
3. Find the `file_path` segment whose basename page label equals `page`. If none → **404**
   (prevents serving arbitrary objects).
4. Normalize that segment to the R2 object key (`<period>/<basename>`, see `data-model.md`).
5. `const obj = await getDocumentsBucket().get(objectKey)`.
   - `null` → **404** (UI placeholder).
   - otherwise stream `obj.body`.

## Responses

### 200 OK
- Body: raw image bytes (streamed).
- Headers:
  - `Content-Type`: `image/jpeg` | `image/png` (from extension; see `data-model.md`).
  - `Cache-Control`: `private, max-age=3600` (auth-gated, so private).

### 403 Forbidden
Unauthenticated / insufficient role.

### 404 Not Found
- The analysis id is unknown, OR
- `page` is not a page of this document (`file_path` has no matching segment), OR
- the R2 object does not exist.

The client treats **any** non-200 as "image unavailable" and shows the placeholder, keeping the rest
of the detail rendered (FR-006, FR-007).

## Security notes
- The `[page]` param can only select among the documented pages of *this* analysis's `file_path`;
  it is never used to build an arbitrary R2 key, so it cannot enumerate other documents' objects.
