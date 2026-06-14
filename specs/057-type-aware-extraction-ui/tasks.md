# Tasks: Type-aware extraction UI

**Feature**: 057-type-aware-extraction-ui
**Spec**: [spec.md](./spec.md) · **Plan**: [plan.md](./plan.md) · **Provenance contract**: [contracts/provenance.md](./contracts/provenance.md)

Tests ARE requested (spec SC-005 + plan): the pure builder + provenance map are unit-tested with the
repo's `node --test` / `.test.mjs` convention.

## Phase 1: Setup

- [x] T001 Confirm the branch + spec dir are in place (`057-type-aware-extraction-ui`) and re-read the current `src/app/dashboard/entries/AttachmentAnalysisDetailDialog.tsx` to anchor the typed branch of `RecordValues` that will be replaced.

## Phase 2: Foundational (blocking prerequisites)

- [x] T002 Add the new i18n keys to `src/lib/i18n/catalog.ts` — under the `analysis` block add: section-title keys (`tsection_general`, `tsection_issuer`, `tsection_provider`, `tsection_recipient`, `tsection_payer`, `tsection_values`, `tsection_totals`, `tsection_retentions`, `tsection_bank`, `tsection_items`, `tsection_duplicates`, `tsection_identified_values`, `tsection_raw_text`) and provenance role labels (`provenance_total`, `provenance_issuer`, `provenance_number`, `provenance_date`, `provenance_service`). Add the same keys to BOTH the pt-BR and en catalogs AND the `Catalog` type, keeping `src/lib/i18n/catalog.test.mjs` parity green. (FR-009)

## Phase 3: User Story 1 — full transcription organized by type (P1)

**Goal**: a typed record renders grouped by the document's structure with localized labels; every transcribed scalar visible; outro/unknown/malformed → generic readable view.
**Independent test**: unit tests build sections for each of the six types + a malformed shape and assert grouping + completeness; browser confirms no crash.

- [x] T003 [US1] Create `src/app/dashboard/entries/typed-transcription.ts`: pure module exporting `ReconRole`, `DocType`, `TypedRow`, `TypedSection` types; `canonicalDocType(value)` (mirrors `type_mappers._canonical_doc_type` alias/normalize/unknown→outro); and `buildTypedSections(values, t, locale)` that walks the typed object — top-level scalars → `general` section, each top-level nested object → its own section (localized title via catalog key when the key is known, else verbatim key), arrays (`itens`/`duplicatas`/`valores_identificados`/retencao numbers) flattened to indexed dotted rows; drops `doc_type`/`schema_version`, keeps `raw_text`; omits empty sections; never throws on partial/odd shapes; currency-formats known amount leaves. No React import beyond `type`-only. (FR-001, FR-002, FR-003)
- [x] T004 [US1] In `AttachmentAnalysisDetailDialog.tsx`, replace the typed branch of `RecordValues` (the current `flattenTyped` block) to call `buildTypedSections` and render each `TypedSection` as a titled grid of `Field`s under the existing `analysis.full_transcription` wrapper; wrap the builder call defensively so any thrown error degrades to the existing generic flatten (keep `flattenTyped` as the fallback). Legacy-flat and error branches untouched. (FR-001, FR-002, FR-007, FR-008)

## Phase 4: User Story 2 — reconciliation provenance highlighting (P1)

**Goal**: the mapper's source fields (total + issuer at minimum; number/date/service where derived) are visibly marked with a role label, consistent with `type_mappers.py`, with no highlight for absent/null targets.
**Independent test**: unit tests assert `RECONCILIATION_PROVENANCE` matches the contract table per type and that `buildTypedSections` tags the right rows; absent target → no role.

- [x] T005 [US2] In `typed-transcription.ts`, add `RECONCILIATION_PROVENANCE: Record<DocType, Partial<Record<ReconRole, string>>>` exactly matching `contracts/provenance.md`, and have `buildTypedSections` tag each row's `provenanceRole` by exact path match against the canonical type's map (array-first-element targets only when the index exists). (FR-004, FR-005, FR-006)
- [x] T006 [US2] In `AttachmentAnalysisDetailDialog.tsx`, render a small role `Badge` (label from the `analysis.provenance_*` catalog key) next to any `Field` whose row carries a `provenanceRole`. (FR-004)

## Phase 5: Tests

- [x] T007 [P] [US1] [US2] Create `src/app/dashboard/entries/typed-transcription.test.mjs` (`node:test`, importing `typed-transcription.ts` directly, asserting role labels resolve from the imported `catalog.ts`): (a) per-type — a representative typed record for danfe/nfse/boleto/recibo/comprovante/outro builds the expected sections and every non-empty value appears (FR-003, SC-001); (b) provenance — `RECONCILIATION_PROVENANCE` equals the contract table and the total+issuer rows are tagged for each type (SC-002); (c) absent/null provenance target → no role tag, no throw (FR-006, SC-004); (d) malformed/partial typed shape (missing sections, null section, non-object) → returns sections without throwing (SC-004); (e) `canonicalDocType` resolves the documented aliases + unknown→outro.

## Phase 6: Polish & verification

- [x] T008 Run `pnpm lint`, `pnpm format`, and `pnpm test:ts` (catalog parity + new builder tests) until green; fix any issues.
- [x] T009 Manual/agent browser verification per `quickstart.md`: dialog renders typed (if present locally) and legacy-flat records with no console/runtime error; provenance badges show for the reconciliation fields.

## Dependencies & order

- T001 → T002 (catalog keys) → T003 (builder, US1) → T004 (component wiring, US1) → T005 (provenance, US2) → T006 (badge render, US2) → T007 (tests) → T008/T009 (polish/verify).
- T005 depends on T003 (same file). T006 depends on T004 + T005. T007 depends on T003 + T005 + T002.
- The two P1 stories share the builder file, so they are sequential (not parallel) by file contention; T007 is `[P]` only relative to T008/T009 documentation/verification.

## MVP

US1 (T003+T004) alone is a shippable improvement (structured transcription). US2 (T005+T006) adds the provenance audit value. Both are P1 and small; ship together.
