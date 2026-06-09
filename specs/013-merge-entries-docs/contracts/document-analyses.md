# Contract: `GET /api/document-analyses`

Existing endpoint. This feature adds **one optional query parameter**; the response shape is unchanged.

## Auth

Session required; `user.role ∈ { admin, member }`, else `403 { error: "Unauthorized" }` (unchanged).

## Request

`GET /api/document-analyses`

| Query param | Type | Required | Behavior |
|-------------|------|----------|----------|
| `period` | string `YYYY-MM` | No | When present, scope results to analyses whose entry belongs to this period (`entries.reportId → accountability_reports.period = period`). When absent, return all analyses across all periods (current behavior). |

An unrecognized/empty `period` value returns an empty array (no error) — it simply matches no period.

## Response — `200 OK`

`DocAnalysisRow[]`, ordered by `analyzedAt DESC` (unchanged shape):

```jsonc
[
  {
    "id": "…", "documentId": "…", "analyzedAt": 1733740800,
    "documentType": "NFS-e", "extractedAmount": 1234.56,
    "amountMatch": true, "extractedCnpj": "…", "issuerName": "…",
    "vendorMatch": false, "extractedDate": "2025-12-03", "dateMatch": true,
    "documentNumber": "…", "serviceDescription": "…", "error": null,
    "entryId": "42", "entryDate": "2025-12-03", "entryDescription": "…",
    "entryAmount": 1234.56, "entryMovementType": "D",
    "vendorName": "…", "subcategoryName": "…", "categoryName": "…"
  }
]
```

## Implementation note

Add `innerJoin(accountabilityReports, eq(entries.reportId, accountabilityReports.id))` and, when `period` is provided, `.where(eq(accountabilityReports.period, period))`. Keep the existing `documents`/`entries`/`vendors`/`subcategories`/`categories` joins and `orderBy(desc(analyzedAt))`.

## Consumers

- `EntriesClient` — calls with `?period=P` to scope the merged page (FR-012).
- `DocumentAnalysisDetailDialog` — unaffected (self-fetches by `id` via `/api/document-analyses/[id]`, `/pages`, `/image/[page]`).

---

## Related (unchanged) contracts

- `GET /api/entries?period=P` — entry rows for a period (unchanged).
- `GET /api/periods` — list of periods (unchanged).
- `GET /api/document-analyses/[id]`, `/[id]/pages`, `/[id]/image/[page]` — detail records & page images (unchanged).
- `GET /dashboard/document-analyses` — now **redirects** (308) to `/dashboard/entries`.
