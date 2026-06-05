---
description: "Task breakdown for: Vision-analyze every page of a document, with per-page parsed results"
---

# Tasks: Vision-analyze every page of a document, with per-page parsed results

**Input**: Design documents from `/specs/003-vlm-analyze-all-pages/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/

**Tests**: No automated test framework is configured (Constitution Principle III). No test tasks
are generated; verification is manual per `quickstart.md`.

**Organization**: Tasks are grouped by user story. NOTE: this feature is unusually file-coupled —
the three P1 stories all edit `scripts/scraper/analise/documentos.py`, so within that file they
are **sequential**, not parallel. Cross-file work (schema, importer) genuinely parallelizes and is
marked `[P]`. The realistic MVP is **US1 + US2 together** (per-page analysis is only observable
through the per-page records); US3 and US4 build on them.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies on incomplete tasks)
- **[Story]**: US1 / US2 / US3 / US4 (maps to spec.md user stories)

## Path Conventions

- Python analysis pass: `scripts/scraper/analise/documentos.py`
- Node importer: `scripts/import-to-d1.mjs`
- Drizzle schema: `src/db/fiscal.schema.ts`; migrations: `drizzle/`

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Confirm the working context before changing code.

- [x] T001 Confirm branch `003-vlm-analyze-all-pages` is checked out and review the four design docs (`plan.md`, `data-model.md`, `research.md`, `contracts/`) so the per-page-record shape and roll-up rules are clear before editing.
- [x] T002 [P] Re-read the current behavior to anchor the diff: `analyze_single_document` (the `first_path = file_path.split(";")[0]` page-1-only logic), `DocAnalysisResult.to_dict`, and `EXTRACT_PROMPT` in `scripts/scraper/analise/documentos.py`; and `escapeSQL` + `TABLE_ORDER` in `scripts/import-to-d1.mjs`.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: The new normalized table must exist before per-page records can be imported (US2/US4)
and before the roll-up's downstream persistence is meaningful. **BLOCKS US2, US3, US4.**

**⚠️ CRITICAL**: No story that emits or imports records can be validated until this phase is done.

- [x] T003 Add the `documentAnalysisRecords` table to `src/db/fiscal.schema.ts` per `data-model.md`: columns `id` (uuid PK), `documentAnalysisId` (text, NOT NULL, FK → `documentAnalyses.id`, **not unique**), `analysisType` text(50) NOT NULL, `pageIndex` integer, `pageLabel` text(20), `artifactRole` text(30), `response` text, `rawText` text, `parseError` text, `analyzedAt` timestamp_ms NOT NULL; plus index `document_analysis_records_document_analysis_id_idx` on `documentAnalysisId`.
- [x] T004 Add Drizzle relations in `src/db/fiscal.schema.ts`: `documentAnalysisRecordsRelations` (`documentAnalysis: one(documentAnalyses, { fields: [documentAnalysisRecords.documentAnalysisId], references: [documentAnalyses.id] })`) and extend `documentAnalysesRelations` with `records: many(documentAnalysisRecords)`.
- [x] T005 Generate and apply the migration: run `pnpm db:generate` (produces `drizzle/0006_*.sql`) then `pnpm db:migrate:dev`; confirm the `document_analysis_records` table + index are created and the migration file is staged for commit (Constitution Principle I — no hand-edited SQL).

**Checkpoint**: New table exists locally; record-emitting and import work can proceed.

---

## Phase 3: User Story 1 - Analyze every page of a multi-page document (Priority: P1) 🎯 MVP

**Goal**: Run one VLM pass per page image for every document, instead of only the first page.

**Independent Test**: Run `analyze-docs` on the evidence period; confirm a 4-page document
triggers 4 VLM passes (one per `;`-separated path) and that a missing/unreadable page is skipped
without aborting the document.

- [x] T006 [US1] In `scripts/scraper/analise/documentos.py`, extract a per-page helper `_analyze_page(model, processor, path) -> tuple[dict | None, str, str | None]` that does the single-image `apply_chat_template` + `generate` (one image per call) and returns `(parsed_dict, raw_text, error)` — reusing `_parse_vlm_response`. This isolates the single-page VLM call that today lives inline in `analyze_single_document`.
- [x] T007 [US1] Rewrite `analyze_single_document` to split `file_path` on `";"` and iterate **all** pages in order (replacing the `first_path = file_path.split(";")[0]` page-1-only path at ~line 168). For each page: if the file is missing/unreadable, record a per-page failure (`parse_error`) and `continue` (do NOT `return`/abort the document); otherwise call `_analyze_page`. Load the model once before the loop. The document-level `error` is set only when **no** page could be read at all.
- [x] T008 [US1] Compute each page's reference: `page_index` (0-based loop position) and `page_label` from the `_pN` filename suffix (regex on the path stem, e.g. `_p3` → `p3`), falling back to `page{index+1}` when no suffix is present. Handle mixed `.jpg`/`.png` extensions (suffix parse is extension-agnostic).

**Checkpoint**: All pages are visited and analyzed; a bad page no longer aborts the document.
(Per-page output is held in memory here; US2 persists it.)

---

## Phase 4: User Story 2 - Preserve each page's parsed result as its own record (Priority: P1)

**Goal**: Emit one structured `page_extraction` record per page, nested under the document
analysis, carrying page reference + artifact role + parsed response (or raw text/error).

**Independent Test**: Analyze a 3-page document → exactly 3 nested `analysis_records` linked to one
`document_analyses` object; a single-page document → exactly 1 record; a parse failure still writes
a record. After the Phase 6 import, rows exist in `document_analysis_records`.

**Depends on**: Phase 2 (table) and Phase 3 (per-page loop produces the per-page data).

- [x] T009 [US2] Add a `PageAnalysisRecord` dataclass to `scripts/scraper/analise/documentos.py` with fields: `document_analysis_id`, `analysis_type` (default `"page_extraction"`), `page_index`, `page_label`, `artifact_role`, `response` (dict | None), `raw_text`, `parse_error`, and a `to_dict()` that emits the keys from `contracts/period-json.md` (id via `det_id("analysis_record", document_id, analysis_type, page_label)`, `analyzed_at` via `now_ms()`). Add a `records: list[PageAnalysisRecord] = field(default_factory=list)` field to `DocAnalysisResult`.
- [x] T010 [US2] Extend `EXTRACT_PROMPT` in `scripts/scraper/analise/documentos.py` to additionally request `"papel_artefato"` (enum `invoice`/`nfse`/`boleto`/`payment_proof`/`other`) per `contracts/page-extraction.schema.json`. (The gross/net/paid value fields are added in T013; doing the role here is what US2's records need for `artifact_role`.)
- [x] T011 [US2] In the per-page loop (T007), build one `PageAnalysisRecord` per page: on success set `response` = parsed dict and `artifact_role` = mapped role (add a small `_map_artifact_role(parsed)` helper that reads `papel_artefato`, defaulting from `tipo_documento`, e.g. `comprovante`→`payment_proof`, `nfs-e`/`nota`→`nfse`, else `other`); on failure set `raw_text` and/or `parse_error` with `response=None`. Append to `result.records`.
- [x] T012 [US2] Update `DocAnalysisResult.to_dict()` to emit a nested `"analysis_records": [r.to_dict() for r in self.records]` key, and stop writing per-page detail into `raw_response` (set it to `None`; keep the legacy column per FR-010). Confirm `_merge_and_write` still replaces the whole object by `document_id` so records persist atomically with their parent.

**Checkpoint**: One `document_analyses` object + N nested `page_extraction` records per document;
failures recorded, not dropped; single-page → 1 record.

---

## Phase 5: User Story 3 - Heterogeneity-aware document roll-up (no false mismatch) (Priority: P1)

**Goal**: Derive document-level fields from all pages and validate `amount_match` against the
paid/net value when a payment artifact is present — killing the false mismatch.

**Independent Test**: Re-analyze the evidence document (`b27329f0-…`, `2025-12`) → `amount_match`
is true, `extracted_amount` ≈ 61590.43 (not 74791.04), and gross+net+paid all remain in the
per-page `response` payloads.

**Depends on**: Phase 4 (records carry roles + values to roll up).

- [x] T013 [US3] Extend `EXTRACT_PROMPT` further to capture `"valor_liquido"` (net after retentions) and `"valor_pago"` (amount actually paid) alongside the existing `"valor_total"` (gross), per `contracts/page-extraction.schema.json`.
- [x] T014 [US3] Add a roll-up function in `scripts/scraper/analise/documentos.py` that derives the document-level fields from `result.records` per `data-model.md`: identity fields (`document_type`, `extracted_cnpj`, `issuer_name`, `extracted_date`, `document_number`, `service_description`) preferring the invoice/nfse record then first-with-value; and `extracted_amount` by precedence **payment_proof `valor_pago` → boleto value → invoice `valor_liquido` (net) → `valor_total` (gross)**, using `_parse_brl_value`. Call it after the page loop in `analyze_single_document`.
- [x] T015 [US3] Apply the existing validations to the rolled-up fields (preserving tolerances): `amount_match` (5% of `entry_amount`) against the precedence-selected amount; `vendor_match` (fuzzy `_normalize_name`) on rolled-up `issuer_name`; `date_match` (`_check_date_in_period`) on rolled-up `extracted_date`. Ensure gross and net are NOT collapsed — both stay only in the per-page `response` (FR-009), never overwritten by the roll-up.

**Checkpoint**: Evidence document's `amount_match` flips false→true; gross/net/paid all recoverable.

---

## Phase 6: User Story 4 - Per-page records survive import into D1 (Priority: P2)

**Goal**: Importer creates one `document_analysis_records` row per nested record and serializes the
`response` object faithfully (no `"[object Object]"`).

**Independent Test**: Import a period with nested records → rows exist linked by
`document_analysis_id`; `SELECT response …` returns valid JSON that `JSON.parse`s back to the
original object.

**Depends on**: Phase 2 (table). Independent of the Python edits in file terms → `[P]` against
Phases 3–5.

- [x] T016 [P] [US4] Fix `escapeSQL` in `scripts/import-to-d1.mjs`: before the `String(value)` fallback (lines ~49-55), add `if (typeof value === "object") { return '\'' + JSON.stringify(value).replace(/'/g, "''") + '\''; }` so objects/arrays (incl. the record `response` and any future nested field) serialize as JSON instead of `"[object Object]"` (FR-012).
- [x] T017 [US4] Add `"document_analysis_records"` to `TABLE_ORDER` in `scripts/import-to-d1.mjs` immediately **after** `"document_analyses"` (FK order; `PRAGMA defer_foreign_keys = ON` already set).
- [x] T018 [US4] In the merge loop of `scripts/import-to-d1.mjs`, for each `document_analyses` row lift its nested `analysis_records` array into `merged["document_analysis_records"]` (dedup by `id`), then `delete row.analysis_records` before the parent row is inserted so the `document_analyses` INSERT contains only real columns. Per `contracts/period-json.md`.

**Checkpoint**: After import, records exist as linked rows and `response` round-trips losslessly.

---

## Phase 7: Polish & Cross-Cutting Concerns

- [x] T019 [P] Run `pnpm lint` and `pnpm format` (and confirm the Python edits read consistently with the surrounding style); ensure `drizzle/0006_*.sql` is committed (Constitution Principle III).
- [ ] T020 Execute `quickstart.md` end-to-end against period `2025-12`: verify SC-001 (N records for N pages), SC-002 (later-page value in roll-up), SC-003 (single-page → 1 record), SC-004 (evidence `amount_match` true + gross/net/paid preserved), SC-005 (JSON round-trip), SC-006 (a second `analysis_type` inserts cleanly), SC-007 (bad page recorded, document not aborted).
- [x] T021 [P] Update `CLAUDE.md` Project Structure / patterns note to mention the `document_analysis_records` table and the "nested `analysis_records` in period JSON, flattened on import" convention, so future agents don't reintroduce the page-1-only assumption.

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: no dependencies.
- **Foundational (Phase 2)**: after Setup. **BLOCKS US2, US3, US4** (the table). US1 can technically
  start in parallel but its output is only persisted/observable once US2 lands.
- **US1 (Phase 3)**: after Setup; produces the per-page data US2 consumes.
- **US2 (Phase 4)**: after Phase 2 (table) **and** Phase 3 (per-page loop).
- **US3 (Phase 5)**: after Phase 4 (records carry roles/values).
- **US4 (Phase 6)**: after Phase 2 (table); file-independent of Phases 3–5 → can be done in parallel.
- **Polish (Phase 7)**: after the stories you intend to ship.

### Critical sequencing inside `documentos.py`

T006 → T007 → T008 (US1) → T009/T010/T011/T012 (US2) → T013/T014/T015 (US3) are **sequential** —
same file, building on each other. Do not parallelize within this file.

### Parallel Opportunities

- T002 [P] alongside T001.
- US4 importer tasks (T016 `[P]`, then T017/T018) run in parallel with the Python work in Phases 3–5
  once Phase 2 is done — different file (`import-to-d1.mjs`).
- T019 [P] and T021 [P] (lint/format and docs) are independent in Polish.

---

## Implementation Strategy

### MVP (ship together): US1 + US2

1. Phase 1 Setup → Phase 2 Foundational (table + migration).
2. Phase 3 (US1 per-page loop) → Phase 4 (US2 records).
3. **STOP and VALIDATE**: a multi-page document yields N nested `page_extraction` records; a bad
   page is recorded, not fatal. This is the core blind-spot fix.

### Increment 2: US3 (correctness payoff)

4. Phase 5 → re-analyze the evidence document → `amount_match` flips false→true. This is the
   user-visible headline fix.

### Increment 3: US4 (durability)

5. Phase 6 → import → confirm rows + JSON round-trip. Can be developed in parallel with US3 since
   it's a different file; just needs the table from Phase 2 and sample nested JSON to import.

6. Phase 7 polish + full `quickstart.md` acceptance sweep.
