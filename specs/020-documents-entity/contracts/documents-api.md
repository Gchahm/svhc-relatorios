# Contract: Documents API

Both routes reuse the standard auth guard (`initAuth` → `getSession` → `ALLOWED_ROLES = ["admin","member"]`, else `403`), and `await getDb()` for D1 access. JSON responses.

## GET /api/documents

List all documents with computed link aggregates. No pagination (dataset is small); client filters/searches in memory or via query params.

**Response** `200`: array of
```jsonc
{
  "id": "string",
  "documentNumber": "string",      // normalized, displayed
  "issuerCnpj": "string",          // 14 digits
  "issuerName": "string | null",
  "documentType": "string | null",
  "totalValue": 1234.56,           // number | null
  "linkedCount": 3,                // count(document_entries)
  "sumEntries": 1300.00,           // sum(live entries.amount) over linked entries
  "status": "over" | "within" | "under" | "unknown"
}
```

- `status` derived server-side: `unknown` when `totalValue` is null; else compare `sumEntries` vs `totalValue` with the same tolerance as `reconcile_group` (5% relative OR R$0.05 absolute) → `within`; `> total` beyond tolerance → `over`; `< total` beyond tolerance → `under`.
- Implementation: Drizzle `select` from `documents` left-joined to a `document_entries`→`entries` aggregate (group by document), `orderBy` issuerName/documentNumber. Tolerance check done in TS after aggregation.

**Errors**: `403` (unauthorized).

## GET /api/documents/[id]

One document plus its linked entries (for the detail dialog).

**Response** `200`:
```jsonc
{
  "id": "string",
  "documentNumber": "string",
  "issuerCnpj": "string",
  "issuerName": "string | null",
  "documentType": "string | null",
  "totalValue": 1234.56,
  "status": "over" | "within" | "under" | "unknown",
  "sumEntries": 1300.00,
  "entries": [
    {
      "entryId": "string",
      "period": "YYYY-MM",         // entry's report period (for the deep link)
      "date": "YYYY-MM-DD",
      "description": "string",
      "amount": 650.00,
      "sourceAttachmentId": "string | null"
    }
  ]
}
```

- Joins `document_entries` → `entries` → `accountability_reports` (for `period`).
- `entries[].period` feeds the deep link `/dashboard/entries?period=<period>&entry=<entryId>` (feature 018).

**Errors**: `403` (unauthorized), `404` (no such document).

## Notes

- Filtering by type and searching by number/issuer MAY be done client-side over the list response (mirrors `VendorsClient`), so no extra query params are required. If added, `?type=` and `?q=` are optional filters applied before returning.
- No write endpoints — documents are produced only by the Python build step.
