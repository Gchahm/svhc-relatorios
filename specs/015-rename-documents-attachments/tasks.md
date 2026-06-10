# Tasks: Rename "documents" → "attachments"

**Feature**: 015-rename-documents-attachments | **Spec**: [spec.md](./spec.md) | **Plan**: [plan.md](./plan.md)
**Inputs**: research.md (keep-vs-rename), data-model.md (exact map), contracts/routes.md, quickstart.md

This is a behavior-preserving rename. Tests are not generated (constitution III — no test framework; verification per quickstart.md). Honor the **KEEP set** from data-model.md (`external_document_id`, `document_type`, `document_number`, `tipo_documento`, `papel_artefato`, `ViewDocuments`, `DOCUMENTS` binding, `fiscal-documents`, `getDocumentsBucket`).

## Phase 1: Setup

- [x] T001 Confirm on branch `015-rename-documents-attachments` and local D1 holds no fiscal rows (already cleared); no dependency install needed (no new deps).

## Phase 2: Foundational (BLOCKS all of US1 — the schema is the contract)

- [x] T002 Rename tables, columns, indexes, and relations in `src/db/fiscal.schema.ts` per data-model.md: `documents`→`attachments`, `documentAnalyses`→`attachmentAnalyses`, `documentAnalysisRecords`→`attachmentAnalysisRecords`; FK fields `documentId`→`attachmentId`, `documentAnalysisId`→`attachmentAnalysisId`; rename the 3 indexes and all relation exports; `entries` relation field `document`→`attachment`. KEEP `externalDocumentId`, `document_type`, `document_number`.
- [x] T003 Generate the migration: `node_modules/.bin/drizzle-kit generate` (per memory: call the binary directly, not `pnpm`). Verify a new `drizzle/<n>.sql` drops the old tables and creates the renamed ones; do not hand-edit it (constitution I).
- [x] T004 Apply locally: `pnpm db:migrate:dev` (or `node_modules/.bin/...`), then assert via wrangler that `attachments`/`attachment_analyses`/`attachment_analysis_records` exist and `documents`/`document_analyses` are gone (quickstart §1).

**Checkpoint**: schema compiles and the renamed tables exist locally.

## Phase 3: User Story 1 — Accurate terminology across the system (P1) 🎯 MVP

**Goal**: Every machine-significant / user-visible reference to the per-entry bundle uses "attachment".
**Independent test**: full pipeline run on a period produces equivalent alerts/roll-ups/mismatches; entries UI renders attachments + page images with no "document" label for the bundle (quickstart §2–4).

### TypeScript app

- [x] T005 [P] [US1] Rename API route dir `src/app/api/document-analyses/` → `src/app/api/attachment-analyses/` (`git mv`), keeping the `[id]`, `[id]/pages`, `[id]/image/[page]` subtree.
- [x] T006 [US1] Update `src/app/api/attachment-analyses/route.ts`: imports `documentAnalyses, documents`→`attachmentAnalyses, attachments`; `documentAnalyses.documentId`→`attachmentAnalyses.attachmentId`; join `documents`→`attachments`; payload field `documentId`→`attachmentId`. (depends on T005)
- [x] T007 [P] [US1] Update `src/app/api/attachment-analyses/[id]/route.ts`, `[id]/pages/route.ts`, `[id]/image/[page]/route.ts`: `documentAnalysisRecords`/`documentAnalyses`/`documents` symbols → attachment-scoped; `documentAnalysisId`→`attachmentAnalysisId`; image URL string `/api/document-analyses/`→`/api/attachment-analyses/`. (depends on T005)
- [x] T008 [US1] `git mv src/app/dashboard/entries/DocumentAnalysisDetailDialog.tsx AttachmentAnalysisDetailDialog.tsx`; rename the component + its props/types `DocumentAnalysis*`→`Attachment*`; update fetch URLs to `/api/attachment-analyses/...`.
- [x] T009 [US1] Update `src/app/dashboard/entries/EntriesClient.tsx`: import + JSX `DocumentAnalysisDetailDialog`→`AttachmentAnalysisDetailDialog`; payload type field `documentId`→`attachmentId`; fetch URL `/api/document-analyses?period=`→`/api/attachment-analyses?period=`; comments + any "document"/"Documento" label for the bundle → "attachment"/"Anexo". (depends on T008)
- [x] T010 [P] [US1] Update `src/lib/r2.ts` doc-comments only: `documents.file_path`→`attachments.file_path`, `document_analysis_records.page_index`→`attachment_analysis_records.page_index`. KEEP `getDocumentsBucket`, `DOCUMENTS`, object-key logic.

### Python pipeline

- [x] T011 [US1] Update `scripts/common/d1.py`: `TABLE_ORDER` entries `documents`/`document_analyses`/`document_analysis_records`→ attachment names; the `analysis_records` flatten branch keys (`document_analyses` guard, `document_analysis_records` target/seen) → attachment names; docstrings. (blocks T012–T017 — shared writer)
- [x] T012 [US1] `git mv scripts/analysis/documentos.py scripts/analysis/attachments.py`; rename `build_document_analysis`→`build_attachment_analysis`, class `DocAnalysisResult`→`AttachmentAnalysisResult`, field/keys `document_id`→`attachment_id`, `document_analysis_id`→`attachment_analysis_id`, internal bundle helpers (`_pick_document_date`/`_document_in_period`/`_pick_document_amount`/issuer picker)→`_*_attachment*`, det-id seed `"doc_analysis"`→`"attachment_analysis"`, writeback SQL table/column names. KEEP `tipo_documento`/`papel_artefato`/`document_type`/`document_number`.
- [x] T013 [US1] Update `scripts/analysis/extractions.py`: import from `.attachments` + `build_attachment_analysis`; raw keys `document_analyses`→`attachment_analyses`; dict keys/params `document_id`→`attachment_id`, `document_ids`→`attachment_ids`, `representative_document_id`→`representative_attachment_id`. (depends on T011, T012)
- [x] T014 [P] [US1] Update `scripts/analysis/loader.py`: SQL `document_analyses`/`document_analysis_records`/`documents`/`da.document_id`/`document_analysis_id`→ attachment names/columns; raw keys; the `analysis_records` re-nest. (depends on T011)
- [x] T015 [P] [US1] Update `scripts/analysis/checks/advanced.py` (raw key `document_analyses`, `analysis_by_doc` keyed on `attachment_id`, `document_ids`→`attachment_ids`, import `..attachments`) and `scripts/analysis/checks/consistency.py` (`check_large_expenses_no_document`→`_no_attachment`, alert type `large_expense_no_document`→`large_expense_no_attachment`, message wording). (depends on T011, T012)
- [x] T016 [P] [US1] Update `scripts/analysis/models.py` (`documents: list[dict]`→`attachments`, `entry_ids_with_documents`→`entry_ids_with_attachments`) and `scripts/analysis/images.py` (`document_ids`→`attachment_ids`, raw key `documents`→`attachments`, comments). (depends on T011)
- [x] T017 [US1] Update `scripts/analysis/verdicts.py` (identity key token `document_id`→`attachment_id`, `_document_ids_of`→`_attachment_ids_of`, `document_ids`→`attachment_ids`, `affected_document_ids`→`affected_attachment_ids`) and `scripts/analysis/__main__.py` (CLI flag `--document-id`→`--attachment-id`, arg `document_ids`→`attachment_ids`, help text). (depends on T011)
- [x] T018 [US1] Update `scripts/scraper/runner.py`: payload keys `documents`→`attachments`, `document_analyses`→`attachment_analyses`; helper `_document_id`→`_attachment_id` + det-id seed `"document"`→`"attachment"`; the writeback `SELECT d.id ... FROM documents`/upsert `{"documents": ...}`→ attachments. KEEP `external_document_id` reads/writes and `documento_ids` (portal). Verify `scripts/scraper/extractors/documentos.py` is left untouched (portal downloader — KEEP per Decision 3).
- [x] T019 [P] [US1] Update `scripts/analysis/nf_groups.py` comments referencing `documentos.py`→`attachments.py` and "document" prose → "attachment" where it means the bundle (KEEP `external_document_id` mention as portal context).

### Pipeline verification (US1)

- [x] T020 [US1] `node_modules/.bin/tsc --noEmit` (or `pnpm build`) passes; run `python -m analysis` import smoke (`python -c "import analysis.attachments, analysis.extractions, analysis.loader"`) from `scripts/`. Fix any missed references surfaced by the grep in quickstart §5.
- [x] T021 [US1] Run the behavior-preserving pipeline on one period (quickstart §2–3): re-scrape (or reuse a fixture), apply-extractions, analyze, mismatches — confirm it completes and the mismatch summary uses `attachment_id`/`attachment_ids`. UI check per §4 (entries page, page images render).

**Checkpoint**: US1 is independently shippable — the rename is complete and behavior-preserving.

## Phase 4: User Story 2 — "Document" reserved as a future-facing concept (P2)

**Goal**: Docs unambiguously reserve "document" for the real N:N entity; no app surface uses it for the bundle.
**Independent test**: a reader of `CLAUDE.md`/`docs` finds the attachment-vs-document distinction and the intended N:N documents↔entries relationship.

- [x] T022 [P] [US2] Update `CLAUDE.md`: rewrite the document-image / document-analysis / shared-NF / duplicate-billing / improve-loop pattern notes to "attachment" terminology; add a short "Attachments vs. Documents" note reserving **document** for the future real-fiscal-document entity that is **N:N with entries** (FR-006, FR-007). Reconcile the auto-appended "Recent Changes/Active Technologies" block.
- [x] T023 [P] [US2] Update `docs/schema-migration-map.md` (`documento`→`attachments`, `analise_documento`→`attachment_analyses`, exports/columns) and any other affected `docs/*.md` (e.g. `docs/features/rollup-amount-false-positives.md`, `docs/SCOPE-fraud-detection.md`) + `README.md` + `scripts/README.md` terminology.
- [x] T024 [P] [US2] Update agent/skill docs that reference the renamed identifiers/tables/routes: `.claude/agents/analyze-docs.md`, `review-mismatch.md`, `fix-mismatch.md` (and `pm.md` if it names the tables); `.claude/skills/classify-period/SKILL.md`, `classify-doc-page/SKILL.md`, `improve-classification/SKILL.md` (`document_id`→`attachment_id`, `--document-id`→`--attachment-id`, `affected_document_ids`→`affected_attachment_ids`, table/route names). Do NOT touch `.claude/skills/speckit/*` (unrelated tooling). KEEP `tipo_documento`/`papel_artefato`/page-record `document_type` references.

**Checkpoint**: US2 complete — the name is documented as reserved.

## Phase 5: Polish & Cross-cutting

- [x] T025 Run the SC-001 grep assertion (quickstart §5): no `documentAnalyses|documentAnalysisRecords|document_analyses|document_analysis_records|'documents'` remains in `src`/`scripts` outside the KEEP set. Fix stragglers.
- [x] T026 `pnpm lint && pnpm format` pass (constitution III). Confirm migration + regenerated schema are committed; `git status` clean except intended changes. Remove the stray untracked `docs/2025-12-classification-known-limitations.md` only if unrelated (leave if pre-existing).

## Dependencies & Order

- **Setup (T001)** → **Foundational (T002→T003→T004)** → **US1 (T005–T021)** → **US2 (T022–T024)** → **Polish (T025–T026)**.
- Within US1: T011 (d1.py writer) and T012 (attachments.py builder) gate the other Python tasks (T013–T019). TS tasks (T005–T010) are independent of the Python tasks and of each other except the noted `git mv` dependencies.
- US2 (docs) depends on US1 being settled so the documented names are final.

## Parallel execution examples

- After T004: run TS group `T005 → (T006, T007)`, `T008 → T009`, `T010` concurrently with Python group `T011 → (T013, T014, T015, T016, T017, T019)` and `T012`.
- US2: T022, T023, T024 are all `[P]` (different files).

## MVP

User Story 1 alone (T001–T021) is the shippable MVP: the rename is complete and behavior-preserving. US2 (docs) is a fast, non-code follow-on that the spec also requires (FR-007).
