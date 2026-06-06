# Data Model: Surface per-page document-analysis detail

**Feature**: 004-doc-analysis-detail | **Date**: 2026-06-06

No schema changes. This documents the existing entities read by the feature and the derived,
non-persisted presentation shapes.

## Existing entities (read-only)

### Document Analysis (roll-up) — `document_analyses`

Surfaced fields (all already returned by the existing list route):

| Field | Type | Notes |
|-------|------|-------|
| `id` | string | analysis id; key for the detail fetch |
| `documentType` | string \| null | e.g. NF-e, DANFE, boleto |
| `extractedAmount` | number \| null | roll-up amount (precedence-derived) |
| `amountMatch` / `vendorMatch` / `dateMatch` | boolean \| null | match flags (already shown as badges) |
| `extractedCnpj` | string \| null | issuer CNPJ — surfaced in detail (FR-002) |
| `issuerName` | string \| null | issuer name — surfaced in detail (FR-002) |
| `documentNumber` | string \| null | surfaced in detail (FR-002) |
| `serviceDescription` | string \| null | surfaced in detail (FR-002) |
| `error` | string \| null | processing error — surfaced in detail (FR-003) |

### Document Analysis Record (per-page) — `document_analysis_records`

One row per page per analysis kind; belongs to one `document_analyses` via `documentAnalysisId`.
Returned by the **new** detail route (FR-004/FR-005).

| Field | Type | Notes |
|-------|------|-------|
| `id` | string | record id |
| `analysisType` | string | e.g. `page_extraction` |
| `pageIndex` | number \| null | 0-based index into the page list |
| `pageLabel` | string \| null | e.g. `p3`; fallback to `page {index+1}` / `?` when null |
| `artifactRole` | string \| null | invoice / nfse / boleto / payment_proof / other |
| `response` | string \| null | JSON-serialized parsed page values (see below) |
| `rawText` | string \| null | VLM raw text, kept when parsing failed |
| `parseError` | string \| null | error when image missing/unreadable or unparseable |

#### Parsed `response` payload (when present and valid JSON)

Keys emitted by the VLM prompt (`scripts/scraper/analise/documentos.py`). All optional / nullable:

| Key | Display label | Render |
|-----|---------------|--------|
| `valor_total` | Gross | currency (BRL) |
| `valor_liquido` | Net | currency (BRL) |
| `valor_pago` | Paid | currency (BRL) |
| `cnpj_emitente` | CNPJ | text |
| `nome_emitente` | Issuer | text |
| `data_emissao` | Issue date | text (DD/MM/YYYY) |
| `numero_documento` | Document № | text |
| `descricao_servico` | Service | text |
| `tipo_documento` | Doc type | text |
| `papel_artefato` | (mirrors artifactRole) | text |
| *(any other key)* | key name | generic string/number |

## Derived presentation values (not persisted)

| Derived value | Source | Used by |
|---------------|--------|---------|
| `reconciledAgainstPayment` | true if any record's `artifactRole ∈ {payment_proof, boleto}` | Story 3 / FR-007 indicator |
| `pageLabelDisplay` | `pageLabel` ?? (`pageIndex != null ? "page " + (pageIndex+1) : "?"`) | per-record header (FR-009) |
| parsed `response` object | `JSON.parse(response)` with try/catch → fallback `rawText`/`parseError` | per-record values (FR-005/FR-009) |

## Validation / invariants

- Detail fetch returns records ordered by `pageIndex` ascending (nulls last) for stable display.
- A non-allowed role MUST receive 403 from the detail route (FR-006); no body data leaks.
- Rendering MUST not throw on null/malformed `response`, null label, or empty record list (FR-009).
