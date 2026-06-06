# Phase 1 Data Model: Vision-analyze every page of a document

## Entities

### `document_analyses` (existing — roll-up, modified semantics)

One row per physical document. Columns unchanged on disk; **semantics** change: every field is
now derived from **all** pages (FR-007), and `amount_match` follows the heterogeneity-aware rule
(FR-008). `raw_response` becomes legacy (nullable, no longer carries per-page detail — FR-010).

| Column | Type | Change |
|--------|------|--------|
| `id` | text PK | unchanged |
| `document_id` | text FK→documents, UNIQUE | unchanged (one analysis per document) |
| `analyzed_at` | timestamp_ms | unchanged |
| `document_type`, `extracted_amount`, `amount_match`, `extracted_cnpj`, `issuer_name`, `vendor_match`, `extracted_date`, `date_match`, `document_number`, `service_description` | as today | now derived across all pages |
| `raw_response` | text | **legacy** — retained nullable, no longer populated with per-page detail |
| `error` | text | unchanged (document-level fatal error, e.g. no pages readable at all) |

Parent of one or more `document_analysis_records`.

### `document_analysis_records` (NEW)

A normalized child record. One row per page **per analysis kind**; many per document, more than
one allowed per page (FR-003, FR-005).

| Column | Type | Constraints | Maps to / meaning |
|--------|------|-------------|-------------------|
| `id` | text PK (uuid) | `det_id("analysis_record", document_id, analysis_type, page_label)` | deterministic, stable across re-runs |
| `document_analysis_id` | text | NOT NULL, FK → `document_analyses.id`, **not unique**, indexed | parent link (FR-004) |
| `analysis_type` | text(50) | NOT NULL | analysis-kind label, e.g. `page_extraction` (FR-004) — discriminator for FR-005 |
| `page_index` | integer | nullable | 0-based index into the `;`-split `file_path` page list |
| `page_label` | text(20) | nullable | `_pN` filename suffix (`p3`) or `page{index+1}` fallback (FR-004) |
| `artifact_role` | text(30) | nullable | `invoice`/`nfse`/`boleto`/`payment_proof`/`other` (FR-004) |
| `response` | text | nullable | JSON-serialized parsed page values (FR-004) — preserves gross/net/paid (FR-009) |
| `raw_text` | text | nullable | VLM raw text; populated when parse failed (and optionally always) |
| `parse_error` | text | nullable | error when image missing/unreadable or unparseable (FR-006) |
| `analyzed_at` | integer (timestamp_ms) | NOT NULL | per-record timestamp |

**Indexes**: `document_analysis_records_document_analysis_id_idx` on `document_analysis_id`;
optional composite on `(document_analysis_id, analysis_type)` for per-kind lookups.

**Relations** (Drizzle): `documentAnalysisRecords.documentAnalysis` → one
`documentAnalyses`; add `records: many(documentAnalysisRecords)` to `documentAnalysesRelations`.

### `entries` (existing — unchanged)

Validation target (amount/vendor/date). Untouched except that the validations it backs are now
derived across all pages.

## Relationships

```
documents (1) ──< (1) document_analyses (1) ──< (N) document_analysis_records
                                                       │  page_index / page_label
                                                       │  analysis_type (page_extraction, …)
                                                       └─ artifact_role + response(JSON)
```

- `documents.entry_id` UNIQUE → one document per entry (out of scope to change here).
- `document_analyses.document_id` UNIQUE → one roll-up per document (FR-002).
- `document_analysis_records.document_analysis_id` **non-unique** → N records per document (FR-003),
  and >1 per page across analysis kinds (FR-005).

## Validation & derivation rules

### Per-page record creation (FR-003, FR-006)
- For each of the `;`-separated page paths in `documents.file_path`, in order:
  - If the file is missing/unreadable → write a record with `parse_error` set, `response`/role
    null; continue to next page (do not abort document).
  - Run one VLM pass; store raw text. If parse fails → record with `raw_text` + `parse_error`.
  - On success → `response` = parsed JSON (stringified), `artifact_role` = mapped role.
- A single-page document yields exactly one `page_extraction` record (SC-003).

### Document-level roll-up (FR-007, FR-008, FR-009)
- **Identity fields** (`document_type`, `extracted_cnpj`, `issuer_name`, `extracted_date`,
  `document_number`, `service_description`): prefer the invoice/nfse record; else first record
  exposing each field.
- **`extracted_amount` / `amount_match`** precedence:
  1. payment_proof paid value → 2. boleto value → 3. invoice net (`valor_liquido`) →
  4. invoice gross (`valor_total`). The chosen amount drives `amount_match` (5% tolerance).
- **`vendor_match`**: fuzzy match issuer_name vs. entry vendor (unchanged logic), using the
  rolled-up `issuer_name`.
- **`date_match`**: date-in-period check (unchanged) on the rolled-up `extracted_date`.
- Gross and net both remain in their pages' `response` JSON — never erased by the roll-up (FR-009).

### Import flattening (FR-011, FR-012)
- Importer reads each `document_analyses` object, lifts its nested `analysis_records` array into
  the `document_analysis_records` table (TABLE_ORDER after `document_analyses`), and removes the
  nested key before inserting the parent row.
- `escapeSQL` serializes object/array values with `JSON.stringify` so `response` round-trips
  (no `"[object Object]"`).
