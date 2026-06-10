# Phase 0 Research: Rename boundary (keep-vs-rename)

The only meaningful design question for a rename is **where the rename stops**. The term "document" appears in three distinct roles in this codebase; conflating them is exactly the bug this feature fixes. Each decision below resolves a `NEEDS CLARIFICATION`-class question of "does this token mean the bundle, the real document, or external infra?"

## Decision 1 — The per-entry bundle ⇒ rename to "attachment"

**Decision**: Rename the entity that today is `documents` (1:1 with an entry) and its analysis chain to attachment-scoped names everywhere it is machine-significant or user-visible.

- DB tables: `documents`→`attachments`, `document_analyses`→`attachment_analyses`, `document_analysis_records`→`attachment_analysis_records`.
- DB FK columns: `document_analyses.document_id`→`attachment_analyses.attachment_id`; `document_analysis_records.document_analysis_id`→`attachment_analysis_records.attachment_analysis_id`. Indexes renamed to match.
- TS: Drizzle exports, all query code, API route segment `document-analyses`→`attachment-analyses`, component `DocumentAnalysisDetailDialog`→`AttachmentAnalysisDetailDialog`, type names, and UI labels.
- Python data-plane identifiers that mirror a DB column or cross the CLI/verdicts/agent boundary: dict key `document_id`→`attachment_id`, `document_ids`→`attachment_ids`, `representative_document_id`→`representative_attachment_id`, payload table keys, the writeback SQL, CLI flag `--document-id`→`--attachment-id`, loop-state `affected_document_ids`→`affected_attachment_ids`, and the builder `build_document_analysis`→`build_attachment_analysis` / class `DocAnalysisResult`→`AttachmentAnalysisResult`.
- Module file `scripts/analysis/documentos.py`→`scripts/analysis/attachments.py` (it builds attachment analyses). Internal helper symbols in that module that describe the bundle (`_pick_document_date`, `_document_in_period`, `_pick_document_amount`, issuer picker) are renamed in-file for consistency.
- The "large expense with no attached file" check: `check_large_expenses_no_document`→`check_large_expenses_no_attachment`, alert type `large_expense_no_document`→`large_expense_no_attachment` (verified: referenced only within `consistency.py`, no frontend coupling).

**Rationale**: This is the core ask (FR-001/002/004/005). Renaming the data-plane `document_id` identifier — not just the DB column — is what actually frees the name "document" for the future N:N entity, which will introduce its own real `document_id`. Leaving the Python id keys as `document_id` would re-introduce the exact ambiguity (FR-006) at the analysis boundary.

**Alternatives rejected**: (a) Rename only the DB tables, keep Python `document_id` keys — rejected: leaves "document" meaning the bundle in the verdicts/agent vocabulary, violating FR-006 and colliding with the future feature. (b) Also rename comments/prose exhaustively — done where cheap, but not gated; prose drift is not behavior and not worth blocking the rename.

## Decision 2 — Real-document properties ⇒ KEEP "document"

**Decision**: Keep `document_type` and `document_number` columns on `attachment_analyses`, and keep the VLM/extraction field names `tipo_documento` / `papel_artefato`.

**Rationale**: These already refer to the **real fiscal document** identified on a page (NF/receipt/boleto) — precisely the concept the feature _reserves_ the word "document" for (FR-006, US2). Renaming them to "attachment" would be _wrong_; they are the lineage the future documents feature builds on.

## Decision 3 — Portal mapping ⇒ KEEP "document"

**Decision**: Keep `external_document_id` (on `entries` and `attachments`), `brcondos_document_id`, the `/Dashboard/ViewDocuments/` URL, and the scraper module `scripts/scraper/extractors/documentos.py` (filename + its portal-facing internal names).

**Rationale**: The brcondos portal's own term is "documento"; these are external-system mappings explicitly carved out by FR-005. They identify the portal record, not our internal entity. `external_document_id` keeps its name so the scrape mapping stays legible; it is the portal id that the new `attachments` row was downloaded against.

## Decision 4 — R2 storage infra ⇒ KEEP "DOCUMENTS"

**Decision**: Retain the R2 binding `DOCUMENTS`, bucket `fiscal-documents`, the accessor `getDocumentsBucket()`, and the entire object-key derivation (`objectKeyFromFilePath`, `parsePage`). Only doc-comments that reference renamed tables/columns are updated.

**Rationale**: Spec Assumptions state page-image storage is preserved and the key-derivation rule is unchanged. Renaming the binding/bucket would require recreating the production R2 bucket and changing `wrangler.toml` + `env.d.ts` for zero behavioral gain — out of proportion to a naming feature, and explicitly out of scope.

## Decision 5 — Data strategy ⇒ drop & recreate (no data migration)

**Decision**: Express the rename in `src/db/fiscal.schema.ts`, run `pnpm db:generate`, and accept the generated migration that drops the old tables and creates the renamed ones. No `ALTER TABLE ... RENAME` data-preserving path. Re-scrape to repopulate.

**Rationale**: FR-008 — fiscal data is reproducible from the portal; local DB is already cleared; production can be re-scraped. Drizzle's SQLite migration for a table rename is a drop+create anyway unless hand-authored, and hand-authoring migrations violates constitution I. det-id seeds may therefore change freely (ids regenerate on re-scrape).

## Decision 6 — Deterministic-id seeds

**Decision**: Update det-id namespace seeds that encode the entity: scraper `_det_id("document", …)`→`"attachment"`, analysis `det_id("doc_analysis", …)`→`"attachment_analysis"`. Keep `"analysis_record"` (records, not the bundle).

**Rationale**: Consistency with the rename; safe because Decision 5 regenerates all ids. The seed must match between the builder (`build_attachment_analysis`) and the writeback/apply path — both updated together.
