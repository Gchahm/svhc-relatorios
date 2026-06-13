# Tasks: Vision Extraction Provenance on Document & Alert Detail

**Feature**: `048-doc-vision-provenance` | **Spec**: [spec.md](./spec.md) | **Plan**: [plan.md](./plan.md)

Presentation-layer feature. No D1 schema change, no migration, no new dependency. All work is in TypeScript under `src/`.

## Phase 1: Setup

- [X] T001 Confirm the working branch is `048-doc-vision-provenance` and the dev toolchain is ready (`node --version` ≥ 22 for `node:test`; `pnpm install` already satisfied). No new dependency to add.

## Phase 2: Foundational (shared plumbing for both P1 stories)

**Blocks US1 and US2** — the document detail client cannot wire the dialog or render provenance until the API supplies the data and the shared selection rule exists.

- [X] T002 Add the pure selection helper `selectReconciliationTotal(pages, rollup)` to `src/lib/documents.ts`: walk `pages` (ordered by page index) and return the first `valor_total` that parses to a finite `> 0` as `{ value, source: "gross", sourcePageLabel }`, else the finite `rollup` as `{ value, source: "rollup", sourcePageLabel: null }`, else `{ value: null, source: "none", sourcePageLabel: null }`. Include a private BRL parser mirroring `_parse_brl_value` (accept number; strip `R$`/non-`[\d,.]`, comma-as-decimal, reject non-finite). Add a DRIFT-GUARD comment binding it to `scripts/analysis/attachments.py:nf_total_for_reconciliation`.
- [X] T003 [P] Add unit cases for the helper to `src/lib/documents.test.mjs` (`node:test`): gross-wins-over-rollup, first-confident-gross-in-order, skip-zero/negative-gross, rollup fallback, none, BRL-string (`"R$ 800,00"`) parsing, and the max-across-analyses attribution scenario.
- [X] T004 [P] Add i18n keys to `src/lib/i18n/catalog.ts` (`CatalogShape` + `pt-BR` + `en` blocks) for: the total-provenance line (e.g. `detail.total_from_page` "extraído da página {page} · {field}", `detail.total_field_gross`, `detail.total_field_rollup` "estimativa consolidada", `detail.total_no_ai` "sem total extraído pela IA"), the "view AI extraction" control (`detail.view_extraction`, `detail.view_extraction_title`, `detail.no_extraction`), and the alert AI-extracted label (`detail.ai_extracted_note`). pt-BR is canonical; provide `en` too.
- [X] T005 Extend `GET /api/documents/[id]` in `src/app/api/documents/[id]/route.ts`:
  - add `extractedAmount: attachmentAnalyses.extractedAmount` to the `sourceRows` select;
  - add `pageIndex: attachmentAnalysisRecords.pageIndex` to the `recordRows` select and parse each record's `response.valor_total` (keep the existing cnpj/number parsing);
  - build a full `AttachmentAnalysisRow` per distinct analysis (mirror the `analysisRows` projection in `src/app/api/alerts/[id]/route.ts`: roll-up fields + the analysis's own entry context via `attachments.entry_id` → entries/vendors/subcategories/categories) and attach it as `analysis` on each `imageSources[]` item;
  - compute `totalProvenance` (top-level, nullable) using `selectReconciliationTotal` per analysis (pages ordered by `pageIndex`), selecting the analysis whose value is the **max** across the document's analyses, and return `{ source, value, analysisId, attachmentId, entryId, period, sourcePageLabel }` (or `null` when there is no analyzed attachment).

**Checkpoint**: `node --test src/lib/documents.test.mjs` and `node --test src/lib/i18n/catalog.test.mjs` pass; the API returns `totalProvenance` + per-source `analysis`.

## Phase 3: User Story 1 — See the AI extraction behind a document's total (P1)

**Goal**: One click from the document detail page opens the existing extraction dialog (roll-up + per-page fields + page image).

**Independent test**: Open a document linked to an analyzed attachment → activate "view AI extraction" → dialog shows per-page extracted values and images.

- [X] T006 [US1] In `src/app/dashboard/documents/[id]/DocumentDetailClient.tsx`: extend the `ImageSource` interface with `analysis: AttachmentAnalysisRow | null`, import `AttachmentAnalysisDetailDialog` and the `AttachmentAnalysisRow` type from `../../entries/`, and add `selectedAnalysis` state + the dialog instance at the bottom of the component (mirror `AlertDetailClient`).
- [X] T007 [US1] Add a "view AI extraction" control on each source-attachment block (in the existing "section_source_attachments" card) that calls `setSelectedAnalysis(source.analysis)`, disabled with `detail.no_extraction` title when `source.analysis` is null; use a lucide icon consistent with the alert page (`Paperclip`/`Sparkles`).

**Checkpoint**: From a document page the dialog opens and shows the AI extraction; documents with no analysis show a disabled control (no error).

## Phase 4: User Story 2 — Trace the total to the exact extracted field (P1)

**Goal**: The header states which page + field (or fallback) produced the total, consistent with the pipeline.

**Independent test**: For a gross-sourced document the header names the page + "invoice gross"; for a fallback document it names the roll-up estimate; for none it says no AI total derived — and the attributed value equals `totalValue`.

- [X] T008 [US2] In `DocumentDetailClient.tsx`: extend `DocumentDetail` with `totalProvenance` (the contract shape), and render a provenance line directly under the `field_total` value in the header card — gross → `detail.total_from_page` with `{page}` = `sourcePageLabel` and `{field}` = `detail.total_field_gross`; rollup → `detail.total_field_rollup`; none/null → `detail.total_no_ai`.
- [X] T009 [US2] Make the provenance line actionable: when `totalProvenance.analysisId` matches a loaded `imageSources[].analysis`, clicking it opens that analysis in the same dialog (reuse `setSelectedAnalysis` from US1) so the reviewer jumps straight to the page/field that set the total. (If US1 is not yet merged, render it as plain text — the line itself is the US2 deliverable.)

**Checkpoint**: Header provenance matches `totalValue`; over/under documents are explainable in one click.

## Phase 5: User Story 3 — Reach the same extraction from an alert (P2)

**Goal**: Total-driven alerts label the disputed figure as AI-extracted; the existing per-entry "View Attachment" dialog reachability is confirmed.

**Independent test**: Open a `document_overpayment` alert → the total figure carries an AI-extracted note; "View Attachment" still opens the extraction dialog.

- [X] T010 [US3] In `src/app/dashboard/alerts/[id]/AlertDetailClient.tsx`, add a localized `detail.ai_extracted_note` annotation in the evidence section for total-driven alert types (e.g. `document_overpayment`, `attachment_amount_mismatch`) so the disputed total is recognizably AI-sourced. Confirm (no code change needed if already present) that each affected entry's "View Attachment" button opens `AttachmentAnalysisDetailDialog`.

**Checkpoint**: Total-driven alerts read as AI-sourced and the extraction dialog is reachable.

## Phase 6: Polish & Cross-Cutting

- [X] T011 [P] Run `pnpm lint` and `pnpm format`; fix any findings. Confirm no raw English literals were added to the affected surfaces (all text via the catalog) and no schema/migration files were generated.
- [X] T012 Verification: `tsc --noEmit` clean, ESLint clean, `node --test src/**/*.test.mjs` 69/69 pass (incl. the new `selectReconciliationTotal` cases), and `pnpm test:e2e` (seed local D1/R2 → Workers build → browser smoke) reported `SMOKE OK — all surface checks passed`. The smoke walk loads the document detail page and the alerts surface, so the extended `/api/documents/[id]` (computing `totalProvenance` + per-source analysis rows) and the new always-rendered provenance line executed without runtime error. Targeted manual browser walk of the new control/dialog states (no-analysis, parse-error) recommended at review.

## Dependencies & Order

- **Setup (T001)** → **Foundational (T002–T005)** → **US1 (T006–T007)** and **US2 (T008–T009)** → **US3 (T010)** → **Polish (T011–T012)**.
- T002 blocks T003 and T005. T004 is independent ([P]). T005 depends on T002.
- US1 and US2 both edit `DocumentDetailClient.tsx`; do US1 then US2 to avoid a merge conflict in the same file (the dialog state US2 reuses is introduced in US1).
- US3 (different file) is independent of US1/US2 once T004's catalog key exists.

## Parallel Opportunities

- T003 (test) and T004 (catalog) run in parallel with each other after/with T002.
- US3 (T010) can proceed in parallel with US1/US2 once T004 is merged (different file).

## Implementation Strategy

**MVP = Foundational + US1 + US2** (both P1): a reviewer can open the AI extraction from the document page *and* see which page/field produced the total — this fully answers the issue's "why R$800?" question. US3 (P2) is a small, independent reinforcement on the alert surface.
