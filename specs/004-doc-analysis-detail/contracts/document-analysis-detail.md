# API Contract: Document Analysis Detail

**Feature**: 004-doc-analysis-detail | **Date**: 2026-06-06

## `GET /api/document-analyses/[id]`

Returns the per-page analysis records for a single document analysis. Read-only.

### Auth

Same guard as `GET /api/document-analyses`:

- Resolve session via `initAuth().api.getSession({ headers })`.
- Require `session.user.role ∈ { "admin", "member" }`.
- Otherwise respond `403 { "error": "Unauthorized" }`.

### Path parameters

| Name | Type | Description |
|------|------|-------------|
| `id` | string | `document_analyses.id` |

### Responses

**200 OK** — JSON array of per-page records, ordered by `pageIndex` ascending (nulls last):

```json
[
  {
    "id": "rec_abc",
    "analysisType": "page_extraction",
    "pageIndex": 0,
    "pageLabel": "p1",
    "artifactRole": "invoice",
    "response": "{\"valor_total\":1500.0,\"valor_liquido\":1350.0,\"cnpj_emitente\":\"12.345.678/0001-90\",\"nome_emitente\":\"ACME LTDA\",\"data_emissao\":\"03/05/2026\",\"numero_documento\":\"NF-12345\",\"descricao_servico\":\"Limpeza\",\"tipo_documento\":\"NF-e\",\"papel_artefato\":\"invoice\"}",
    "rawText": null,
    "parseError": null
  },
  {
    "id": "rec_def",
    "analysisType": "page_extraction",
    "pageIndex": 1,
    "pageLabel": "p2",
    "artifactRole": "payment_proof",
    "response": "{\"valor_pago\":1350.0,\"data_emissao\":\"05/05/2026\",\"papel_artefato\":\"payment_proof\"}",
    "rawText": null,
    "parseError": null
  }
]
```

Notes:
- `response` is a JSON **string** (as stored). The client parses it; on parse failure it falls back
  to `rawText` / `parseError`.
- An analysis with no records returns `[]` (200), not 404. The client renders an empty state.

**403 Forbidden** — caller lacks an allowed role:

```json
{ "error": "Unauthorized" }
```

### Behavior contract

- MUST query only `document_analysis_records` filtered by `documentAnalysisId = id`.
- MUST NOT mutate any data.
- MUST NOT change the response shape of the existing list route.
- Ordering by `pageIndex` ascending; records with null `pageIndex` sort last.

## Existing routes (unchanged)

`GET /api/document-analyses` continues to return the roll-up list payload it returns today,
including `issuerName`, `extractedCnpj`, `documentNumber`, `serviceDescription`, `documentType`,
and `error` — which the detail dialog reads from the already-loaded row.
