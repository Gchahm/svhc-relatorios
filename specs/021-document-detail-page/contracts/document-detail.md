# Contract: `GET /api/documents/[id]` (extended)

Auth-gated (roles `admin`, `member`; else `403`). Returns the full detail view model for one document.
This **extends** the existing endpoint (which already returned the header + a basic `entries` list);
new fields are `category`/`subcategory`/`vendor`/`unitCode` on each entry, plus `imageSources` and
`relatedDocuments`. Existing consumers tolerate additive fields.

## Request

```
GET /api/documents/{id}
```

- `id` — `documents.id`.

## Responses

### 200 OK

```json
{
  "id": "det_doc_…",
  "documentNumber": "12345",
  "issuerCnpj": "12345678000199",
  "issuerName": "ACME Serviços Ltda",
  "documentType": "NFS-e",
  "totalValue": 1500.0,
  "sumEntries": 1500.0,
  "status": "within",
  "entries": [
    {
      "entryId": "det_entry_…",
      "period": "2025-12",
      "date": "2025-12-03",
      "description": "Manutenção elevador",
      "amount": 750.0,
      "category": "Manutenção",
      "subcategory": "Elevadores",
      "vendor": "ACME Serviços Ltda",
      "unitCode": null,
      "sourceAttachmentId": "det_att_…"
    }
  ],
  "imageSources": [
    {
      "attachmentId": "det_att_…",
      "analysisId": "det_an_…",
      "entryId": "det_entry_…",
      "period": "2025-12"
    }
  ],
  "relatedDocuments": [
    {
      "id": "det_doc_other_…",
      "documentNumber": "67890",
      "issuerCnpj": "98765432000111",
      "issuerName": "Banco X",
      "documentType": "boleto",
      "totalValue": 750.0,
      "sumEntries": 750.0,
      "status": "within"
    }
  ]
}
```

- `entries` ordered by `period`, then `date`.
- `imageSources` — one per distinct provenance attachment that has an analysis (deduped by
  `analysisId`); empty when none.
- `relatedDocuments` — other documents sharing ≥1 entry with the subject (subject excluded); empty
  when none; ordered by `issuerName`, then `documentNumber`.

### 403 Forbidden

```json
{ "error": "Unauthorized" }
```

### 404 Not Found

```json
{ "error": "Not found" }
```

Returned when no `documents` row has the given `id` (drives the page's "not found" state, FR-010).

## Reused contracts (unchanged)

The page consumes the existing attachment page-image routes, passing an `analysisId` from
`imageSources`:

- `GET /api/attachment-analyses/{analysisId}/pages` → `[{ pageIndex, pageLabel, ext, imageUrl }]`
- `GET /api/attachment-analyses/{analysisId}/image/{pageLabel}` → image bytes (R2-streamed)

A 404/empty from either is non-fatal: the page renders without that source's image (FR-009).
