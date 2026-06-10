# Phase 1 Data Model: Remove `.classify.json` — per-page extractions to D1

## New entity: Page classification (`page_classifications`)

The raw per-page vision result for one page of one attachment — the merge step's per-page
extraction **input**. One row per (attachment, page label). Not surfaced to end users.

### Fields

| Field            | Type (D1 / Drizzle)                 | Notes                                                                                   |
|------------------|-------------------------------------|-----------------------------------------------------------------------------------------|
| `id`             | text, PK                            | Deterministic: `det_id("page_classification", attachment_id, page_label)` — so a re-record of the same page hits the same row (idempotent upsert). |
| `attachment_id`  | text, NOT NULL, FK → `attachments.id` | The attachment this page belongs to (the representative attachment of its NF group).    |
| `page_label`     | text(20), NOT NULL                  | e.g. `p3` (from the `_pN` suffix) or `pageN` — derived by `_page_label_from_path`.      |
| `page_index`     | integer, nullable                   | 0-based index into the attachment's `file_path` page list (reference/debug; not the key).|
| `response`       | text (JSON), nullable               | The extracted fields object, JSON-serialized. NULL when the page is an error result.    |
| `error`          | text, nullable                      | Short error reason (the skill's `{"error": …}`). NULL on a successful fields object.     |
| `recorded_at`    | integer (timestamp_ms), NOT NULL    | When the extraction was recorded (`now_ms()`).                                          |

### Keys / indexes

- **Primary key**: `id` (deterministic on `attachment_id` + `page_label`).
- **Uniqueness**: the deterministic `id` enforces one row per (attachment, page label) — re-recording
  replaces it via `INSERT OR REPLACE` (FR-002, SC-004).
- **Index**: `page_classifications_attachment_id_idx` on `attachment_id` (the merge / loader read by
  attachment).

### Invariants

- Exactly one of (`response`, `error`) is populated; never both, never neither (the validator and
  the skill contract enforce this — an extraction is *either* the full fields object *or*
  `{"error": "<reason>"}`).
- `response`, when present, conforms to the **frozen page-field contract** (see below). It is stored
  as the raw fields object (gross/net/paid amounts, issuer, dates, etc.) — the same shape previously
  written to `<image>.classify.json` and persisted into `attachment_analysis_records.response`.

### Lifecycle

1. **Record** — `record-classification` (called by `classify-doc-page`) validates the payload and
   `INSERT OR REPLACE`s the row keyed by the deterministic id.
2. **Read** — `apply-extractions` (via the loader) batch-loads the period's rows; the
   `D1ExtractionProvider` serves `(attachment_id, page_label) → (fields|None, error|None)`.
3. **Consume** — the merge builds `attachment_analyses` + `attachment_analysis_records` from the
   provider output (roll-up / reconcile / fan-out unchanged) and stamps `attachments.classified_at`.
4. **Re-record** — marking the attachment pending (`mark-pending`) and re-classifying overwrites the
   page row (same deterministic id); the next merge rebuilds from the fresh extraction.

The staging rows are **not** deleted by the merge — they remain as the recorded vision input, so a
re-run of the merge alone (without re-classifying) reproduces the same analyses (FR-005, SC-001).

## Frozen page-field contract (unchanged; enforced at record time)

The `response` object must contain exactly these keys (mirrors
`.claude/skills/classify-doc-page/templates/result.json` and `validate_classify.py`):

- `papel_artefato` ∈ `invoice | nfse | boleto | payment_proof | other`
- `tipo_documento` ∈ `NF-e | DANFE | boleto | recibo | comprovante | outro` or `null`
- `valor_total`, `valor_liquido`, `valor_pago` — number, currency string, or `null`
- `cnpj_emitente`, `nome_emitente`, `data_emissao`, `numero_documento`, `descricao_servico` —
  string or `null`

The one permitted alternative is `{ "error": "<non-empty string>" }` (exactly that key).

## Extraction-provider seam (changed signature)

The seam in `attachments.build_attachment_analysis` changes from path-keyed to identity-keyed:

- **Before**: `provider(path: str) -> (fields|None, error|None)` (file-backed —
  `FileExtractionProvider` reads `<image>.classify.json`).
- **After**: `provider(attachment_id: str, page_label: str) -> (fields|None, error|None)`
  (D1-backed — `D1ExtractionProvider` serves from the batch-loaded `page_classifications` map).

Return contract is unchanged: `(fields, None)` for a fields object, `(None, reason)` for an error
result, `(None, "no classification for page …")` when no row exists. So `build_attachment_analysis`'s
per-page record creation, the "no page produced a parseable response" handling, and the rest of the
roll-up are untouched.

## Removed columns (dead since the local-VLM path was retired)

| Table                          | Column         | Why removed                                                        |
|--------------------------------|----------------|--------------------------------------------------------------------|
| `attachment_analyses`          | `raw_response` | Legacy VLM raw text; never populated by the Claude flow.           |
| `attachment_analysis_records`  | `raw_text`     | Legacy VLM raw text kept on parse failure; never populated now.    |

Removed via a generated, committed Drizzle migration. Code/UI references removed:
`AttachmentAnalysisResult.raw_response`, `PageAnalysisRecord.raw_text` (+ `to_dict` and `_fanout_result`
copies), `route.ts` select of `rawText`, and the detail dialog's `rawText` field/fallback/render.
