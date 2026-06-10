# Contracts: API routes (renamed, no new endpoints)

No new endpoints. The existing attachment-analysis endpoints are renamed `document-analyses` → `attachment-analyses`. Request/response shapes are unchanged except the field `documentId` → `attachmentId` in the list payload.

| Before                                         | After                                            | Notes                                            |
| ---------------------------------------------- | ------------------------------------------------ | ------------------------------------------------ |
| `GET /api/document-analyses?period=<p>`        | `GET /api/attachment-analyses?period=<p>`        | list; payload field `documentId`→`attachmentId`  |
| `GET /api/document-analyses/[id]`              | `GET /api/attachment-analyses/[id]`              | per-attachment page records                      |
| `GET /api/document-analyses/[id]/pages`        | `GET /api/attachment-analyses/[id]/pages`        | page list; image URLs point at the renamed route |
| `GET /api/document-analyses/[id]/image/[page]` | `GET /api/attachment-analyses/[id]/image/[page]` | streams page bytes from R2                       |

All routes remain auth-gated exactly as before (constitution IV). Internal callers (`EntriesClient.tsx`, the detail dialog) are updated in lockstep; there are no external consumers.

## Retained for backward compatibility

`GET /dashboard/document-analyses` (page route) stays as a redirect shim to `/dashboard/entries` — it preserves old human bookmarks to the _former URL_ and is not part of the entity rename.
