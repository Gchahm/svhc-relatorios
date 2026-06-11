# Contract: `GET /api/alerts/[id]` (new)

Auth-gated (roles `admin`, `member`; else `403`). Returns the full alert for the detail page.

## Request

```
GET /api/alerts/{id}
```

- `id` — `alerts.id`.

## Responses

### 200 OK

```json
{
  "id": "…",
  "type": "document_overpayment",
  "severity": "critical",
  "title": "Document over-claimed",
  "description": "Linked entries sum R$ 34.396,11 above the invoice total R$ 30.174,64 …",
  "referencePeriod": "2026-01",
  "createdAt": 1767225600000,
  "resolved": false,
  "resolvedAt": null,
  "notes": null,
  "metadata": "{\"document_id\":\"a545…\",\"total_value\":30174.64,\"sum_entries\":34396.11,\"over_amount\":4221.47,\"entry_ids\":[\"c9eb…\"]}"
}
```

- `metadata` is the raw JSON text (parsed client-side); may be `null`.
- `createdAt` / `resolvedAt` are epoch milliseconds (`resolvedAt` null when active).
- `entries` — the affected entries (resolved from `metadata.entry_ids`/`entry_id`), each with full
  detail and its attachment analysis + linked documents for the per-entry modals:

```json
{
  "entries": [
    {
      "entryId": "…", "period": "2026-01", "date": "2026-01-20",
      "description": "ENERGIA ELÉTRICA - ENERGIA ELÉTRICA",
      "amount": 101.76, "movementType": "D",
      "category": "Consumo", "subcategory": "ENERGIA ELETRICA",
      "vendor": "CELESC DISTRIBUICAO S.A", "unitCode": null,
      "analysis": { "id": "…", "attachmentId": "…", "documentType": "DANFE", "…": "… (AttachmentAnalysisRow shape, or null)" },
      "documents": [
        { "id": "…", "documentNumber": "4598567", "issuerName": "CELESC …", "documentType": "DANFE", "totalValue": 101.76 }
      ]
    }
  ]
}
```

- `analysis` is `null` when the entry has no attachment analysis; `documents` is `[]` when none.
- `analysis` matches the shape of `GET /api/attachment-analyses` rows so the entries-view detail
  modal consumes it directly and self-fetches its page images by `analysis.id`.

### 403 Forbidden

```json
{ "error": "Unauthorized" }
```

### 404 Not Found

```json
{ "error": "Alert not found" }
```

Returned when no `alerts` row has the given `id` (drives the "not found" state, FR-011).
