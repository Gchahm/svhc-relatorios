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

### 403 Forbidden

```json
{ "error": "Unauthorized" }
```

### 404 Not Found

```json
{ "error": "Alert not found" }
```

Returned when no `alerts` row has the given `id` (drives the "not found" state, FR-011).
