# Contract: period JSON shape & importer flattening

## Period JSON (`data/scrape/<period>.json`) — `document_analyses` with nested records

Each entry of the top-level `document_analyses` array gains a nested `analysis_records` array.
This is what `DocAnalysisResult.to_dict()` emits and what `_merge_and_write` persists (replacing
the whole object by `document_id`).

```jsonc
{
  "document_analyses": [
    {
      "id": "doc_analysis-…",
      "document_id": "…",
      "analyzed_at": 1733424000000,
      "document_type": "nfse",
      "extracted_amount": 61590.43,          // rolled up — paid/net, NOT gross
      "amount_match": 1,                       // true after the fix (was 0)
      "extracted_cnpj": "47.318.128/0001-61",
      "issuer_name": "EVO SERVIÇOS",
      "vendor_match": 1,
      "extracted_date": "15/12/2025",
      "date_match": 1,
      "document_number": "…",
      "service_description": "…",
      "raw_response": null,                    // legacy — no longer per-page detail
      "error": null,
      "analysis_records": [                     // NEW — nested, one per page per analysis kind
        {
          "id": "analysis_record-…",
          "document_analysis_id": "doc_analysis-…",
          "analysis_type": "page_extraction",
          "page_index": 0,
          "page_label": "p1",
          "artifact_role": "nfse",
          "response": { "papel_artefato": "nfse", "valor_total": 74791.04,
                        "valor_liquido": 61590.43, "cnpj_emitente": "47.318.128/0001-61" },
          "raw_text": null,
          "parse_error": null,
          "analyzed_at": 1733424000000
        },
        { "…": "page_index 1 — nfse stub" },
        { "…": "page_index 2 — boleto, valor 61590.43" },
        { "…": "page_index 3 — payment_proof, valor_pago 61590.43" }
      ]
    }
  ]
}
```

Notes:
- `response` is an **object** in the JSON (the importer serializes it to a JSON string on insert).
- A failed page still appears as a record with `parse_error` (and `raw_text` when available),
  `response: null` (FR-006).

## Importer behavior (`scripts/import-to-d1.mjs`)

1. Add `"document_analysis_records"` to `TABLE_ORDER` **immediately after** `"document_analyses"`
   (FK ordering; `PRAGMA defer_foreign_keys = ON` already set).
2. During merge, for each `document_analyses` row: pull `row.analysis_records` (default `[]`),
   push each into `merged["document_analysis_records"]` (dedup by `id`), then delete
   `row.analysis_records` so the parent insert only has real columns.
3. `escapeSQL`: add, before the `String(value)` fallback —
   ```js
   if (typeof value === "object") {  // arrays included; null handled above
       const str = JSON.stringify(value).replace(/'/g, "''");
       return `'${str}'`;
   }
   ```
   so `response` (and any future nested field) round-trips instead of becoming `"[object Object]"`.

## Round-trip guarantee (FR-011, SC-005)

`JSON.parse(row.response)` read back from D1 equals the original parsed page object — verified in
quickstart by querying a known record after import.
