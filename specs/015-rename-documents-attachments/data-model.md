# Phase 1 Data Model: Rename map

Behavior-preserving rename. The relational shape is **unchanged** — same rows, same FKs, same indexes — only names change. No new entity is added (FR-009).

## Tables

| Before (table)              | After (table)                 | Drizzle export before → after                           |
| --------------------------- | ----------------------------- | ------------------------------------------------------- |
| `documents`                 | `attachments`                 | `documents` → `attachments`                             |
| `document_analyses`         | `attachment_analyses`         | `documentAnalyses` → `attachmentAnalyses`               |
| `document_analysis_records` | `attachment_analysis_records` | `documentAnalysisRecords` → `attachmentAnalysisRecords` |

Relations renamed to match: `documentsRelations`→`attachmentsRelations`, `documentAnalysesRelations`→`attachmentAnalysesRelations`, `documentAnalysisRecordsRelations`→`attachmentAnalysisRecordsRelations`. The `entries` relation field `document: one(documents)` → `attachment: one(attachments)`.

## Columns

### `attachments` (was `documents`)

| Before                          | After                  | Notes                                  |
| ------------------------------- | ---------------------- | -------------------------------------- |
| `id`                            | `id`                   | unchanged                              |
| `entry_id` (unique, FK→entries) | `entry_id`             | unchanged — one attachment per entry   |
| `external_document_id`          | `external_document_id` | **KEEP** — portal mapping (Decision 3) |
| `file_path`                     | `file_path`            | unchanged — `;`-joined R2 keys         |

Drizzle field `entryId` unchanged; `externalDocumentId` unchanged. Index `documents_entry_id_idx` → `attachments_entry_id_idx`.

### `attachment_analyses` (was `document_analyses`)

| Before                                                                                                                                                                                                 | After                               | Notes                                          |
| ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | ----------------------------------- | ---------------------------------------------- |
| `document_id` (FK→documents.id)                                                                                                                                                                        | `attachment_id` (FK→attachments.id) | **RENAME** (field `documentId`→`attachmentId`) |
| `document_type`                                                                                                                                                                                        | `document_type`                     | **KEEP** — real-document property (Decision 2) |
| `document_number`                                                                                                                                                                                      | `document_number`                   | **KEEP** — real-document property (Decision 2) |
| all other columns (`analyzed_at`, `extracted_amount`, `amount_match`, `extracted_cnpj`, `issuer_name`, `vendor_match`, `extracted_date`, `date_match`, `service_description`, `raw_response`, `error`) | unchanged                           |                                                |

Index `document_analyses_document_id_idx` → `attachment_analyses_attachment_id_idx`.

### `attachment_analysis_records` (was `document_analysis_records`)

| Before                                                                                                                                 | After                                                | Notes                                                          |
| -------------------------------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------- | -------------------------------------------------------------- |
| `document_analysis_id` (FK→document_analyses.id)                                                                                       | `attachment_analysis_id` (FK→attachment_analyses.id) | **RENAME** (field `documentAnalysisId`→`attachmentAnalysisId`) |
| all other columns (`analysis_type`, `page_index`, `page_label`, `artifact_role`, `response`, `raw_text`, `parse_error`, `analyzed_at`) | unchanged                                            |                                                                |

Index `document_analysis_records_document_analysis_id_idx` → `attachment_analysis_records_attachment_analysis_id_idx`.

### `entries` — unchanged

`entries.external_document_id` is **kept** (portal mapping). No change to the entries table.

## Python identifier rename (data-plane)

These are not DB columns but flow across the CLI / verdicts JSON / agent boundary and must track the rename to free "document":

| Before                                                                            | After                                                                |
| --------------------------------------------------------------------------------- | -------------------------------------------------------------------- |
| payload/raw key `"documents"`                                                     | `"attachments"`                                                      |
| payload/raw key `"document_analyses"`                                             | `"attachment_analyses"`                                              |
| table key `"document_analysis_records"` (d1 flatten)                              | `"attachment_analysis_records"`                                      |
| nested roll-up key `"analysis_records"`                                           | `"analysis_records"` (KEEP — records of analysis)                    |
| dict key / param `document_id`                                                    | `attachment_id`                                                      |
| dict key / param `document_ids`                                                   | `attachment_ids`                                                     |
| `representative_document_id`                                                      | `representative_attachment_id`                                       |
| `document_analysis_id`                                                            | `attachment_analysis_id`                                             |
| CLI flag `--document-id`                                                          | `--attachment-id`                                                    |
| loop-state `affected_document_ids`                                                | `affected_attachment_ids`                                            |
| builder `build_document_analysis`                                                 | `build_attachment_analysis`                                          |
| class `DocAnalysisResult`                                                         | `AttachmentAnalysisResult`                                           |
| `models.PeriodData.documents` / `entry_ids_with_documents`                        | `attachments` / `entry_ids_with_attachments`                         |
| det-id seed `"document"` (scraper), `"doc_analysis"` (analysis)                   | `"attachment"`, `"attachment_analysis"`                              |
| check `check_large_expenses_no_document` / alert type `large_expense_no_document` | `check_large_expenses_no_attachment` / `large_expense_no_attachment` |

**KEEP** (Decisions 2–4): `external_document_id`, `brcondos_document_id`, `tipo_documento`, `papel_artefato`, `document_type`, `document_number`, `ViewDocuments`, `DOCUMENTS` binding, `fiscal-documents`, `getDocumentsBucket`.

## Mismatch identity (verdicts) — unchanged semantics, renamed key

The mismatch identity key changes only the token name: `period|kind|document_id|entry_id` → `period|kind|attachment_id|entry_id`; duplicate-billing `period|kind|sorted(document_ids)` → `period|kind|sorted(attachment_ids)`. Because data is re-scraped (Decision 5), no existing `*.verdicts.json` needs migrating.

## Reserved (future, NOT created here)

- **Document** — a real fiscal document (NF/receipt/boleto) identified from attachment pages, **N:N with entries**. No table, no join, no `document_id` column is created by this feature; the name is simply left free and documented (US2, FR-009).
