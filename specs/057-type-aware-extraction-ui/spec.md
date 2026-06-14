# Feature Specification: Type-aware extraction UI

**Feature Branch**: `057-type-aware-extraction-ui`  
**Created**: 2026-06-14  
**Status**: Draft  
**Input**: User description: "Type-aware extraction UI: render the full typed transcription per document type (DANFE/NFS-e/boleto/recibo/comprovante/outro) in AttachmentAnalysisDetailDialog, highlighting the derived reconciliation fields with provenance, with a generic JSON-tree fallback for outro/unknown, dual-path support for legacy flat rows, and all new labels via the pt-BR i18n catalog."

## Context

The attachment analysis detail dialog is where a reviewer confirms an AI extraction against the source page image. Since feature 055 (EXTRACT-004) a per-page stored extraction can be a **typed transcription** — a rich, per-document-type JSON object (an NFS-e records `valores.valor_liquido`, a DANFE records `totais.valor_total_nota`, etc.) — or a **legacy flat record** (the pre-typed ~10-field reconciliation object). Today the dialog renders a typed record as a flat alphabetical dump of dotted key paths under a single "Full transcription" heading, which loses the document's structure and gives the reviewer no signal about *which* transcribed field became the reconciliation total/issuer/number the alerts are computed from.

This feature makes the dialog **type-aware**: it presents the whole transcription organized the way the document is laid out, and visibly marks the fields the deterministic mapper derived the reconciliation values from (the provenance), so a reviewer can confirm "the total the system reconciled on is the one I see on the page" at a glance. The reconciliation derivation itself is unchanged — it is the deterministic per-type mapper already shipped (feature 053 / EXTRACT-003).

## User Scenarios & Testing *(mandatory)*

### User Story 1 - See the full transcription organized by document type (Priority: P1)

A reviewer opens the analysis detail dialog for an entry whose attachment was transcribed into a typed record (e.g. an NFS-e). Instead of a flat alphabetical key dump, they see the transcription grouped into the document's natural sections (issuer/prestador, recipient/tomador, values, retentions, etc.), with friendly section and field labels in their language, so they can read the document the way it is laid out and cross-check it against the page image.

**Why this priority**: This is the original request ("show all the text that exists in the document") and the core of the issue — without it the reviewer cannot efficiently confirm the extraction.

**Independent Test**: Open the dialog on a seeded NFS-e typed record and confirm the values appear under recognizable grouped sections with translated labels, matching what the page image shows.

**Acceptance Scenarios**:

1. **Given** an attachment whose page response is a typed NFS-e transcription, **When** the reviewer opens the analysis dialog, **Then** the page record renders the transcription grouped into its document sections (provider, recipient, values, retentions) with localized labels and every transcribed scalar value visible.
2. **Given** a typed DANFE / boleto / recibo / comprovante transcription, **When** the dialog opens, **Then** the corresponding type-specific layout is used and all transcribed fields are shown.
3. **Given** a typed record of an unrecognized or `outro` document type, **When** the dialog opens, **Then** a generic readable rendering of the whole transcription is shown (no fields dropped, no crash).

### User Story 2 - Reconciliation fields highlighted with provenance (Priority: P1)

A reviewer needs to know which transcribed field the system used as the reconciliation total / issuer / document number (the values that drive amount/vendor/date matches and alerts). In the transcription view, those source fields are visually marked and labelled with the reconciliation role they feed (e.g. "total reconciliado", "emissor"), so the reviewer can immediately verify the system reconciled on the right number.

**Why this priority**: Provenance is the audit value — it closes the loop between the raw transcription and the alert math, and is explicitly required by the issue.

**Independent Test**: On a seeded NFS-e typed record, confirm the `valores.valor_liquido` field is marked as the reconciliation total and the `prestador` is marked as the issuer, matching the derivation in the Python mapper.

**Acceptance Scenarios**:

1. **Given** a typed NFS-e transcription, **When** the dialog opens, **Then** the `valores.valor_liquido` field is highlighted and labelled as the reconciliation total, and the `prestador` (name/cnpj) is marked as the issuer.
2. **Given** a typed DANFE transcription, **When** the dialog opens, **Then** `totais.valor_total_nota` is highlighted as the reconciliation total and `emitente` as the issuer.
3. **Given** a typed boleto / recibo / comprovante transcription, **When** the dialog opens, **Then** the field the mapper uses for that type's total (valor_documento / valor / valor) and issuer (beneficiario / recebedor) is highlighted accordingly.
4. **Given** a typed transcription whose provenance source field is absent or null, **When** the dialog opens, **Then** no provenance highlight is shown for that missing field and no error occurs.

### User Story 3 - Legacy flat rows still render unchanged (Priority: P2)

A reviewer opens the dialog for an attachment classified before typed transcription existed (a legacy flat record). It renders exactly as it did before — the known reconciliation fields with their friendly labels — so older periods are unaffected.

**Why this priority**: No-regression guarantee for the existing data; the dual-path behavior already established in feature 055 must be preserved.

**Independent Test**: Open the dialog on a seeded legacy flat record and confirm it renders the same flat known-field grid as before, with no typed-section layout.

**Acceptance Scenarios**:

1. **Given** a page response that is a legacy flat record (no `doc_type` key), **When** the dialog opens, **Then** it renders the known reconciliation fields exactly as the pre-feature behavior (no typed section layout, no provenance highlights).
2. **Given** a page response that is an `{"error": ...}` record or unparseable, **When** the dialog opens, **Then** the existing error/no-values behavior is shown unchanged.

### Edge Cases

- A typed transcription with a partial/odd shape (missing nested sections, null sections): degrades to showing whatever scalar values are present without dropping the whole record or crashing.
- A typed transcription declaring a `doc_type` whose canonical type has no dedicated layout: falls back to the generic readable rendering (same as `outro`).
- A typed transcription where a section exists but contains only null/empty values: that section is omitted (no empty noise).
- Very long verbatim text fields (e.g. `raw_text`, `discriminacao_servico`): render readably without breaking the dialog layout.
- The reconciliation provenance must stay consistent with the Python mapper; if the mapper changes a derivation, the UI highlight must reflect the same source field (single shared source of truth for the provenance map).

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The analysis detail dialog MUST render a typed transcription record organized by the document's natural structure, per document type (DANFE, NFS-e, boleto, recibo, comprovante de pagamento), rather than a flat alphabetical key dump.
- **FR-002**: For a typed record whose document type is `outro` or any unrecognized/unmapped type, the dialog MUST render a generic readable view of the entire transcription with no fields dropped and no crash.
- **FR-003**: Every transcribed scalar value present in a typed record MUST be visible to the reviewer (the "show all the text" requirement) — no silent omission of non-empty fields.
- **FR-004**: The dialog MUST visually highlight and label the transcribed fields the deterministic reconciliation mapper derives its values from (at minimum: the reconciliation total and the issuer), labelled with the reconciliation role they feed.
- **FR-005**: The provenance highlighting MUST be consistent with the deterministic per-type mapper's derivation (the same source field per document type), maintained as a single shared definition so the UI cannot drift from the mapper.
- **FR-006**: When a provenance source field is absent or null for a given record, the dialog MUST NOT show a highlight for it and MUST NOT error.
- **FR-007**: The dialog MUST continue to render legacy flat records (responses with no `doc_type` discriminator) exactly as the pre-feature behavior, with no typed layout or provenance highlights.
- **FR-008**: The dialog MUST continue to render `{"error": ...}` and unparseable responses with the existing error/no-values behavior.
- **FR-009**: All new user-facing chrome introduced by this feature (section headings, field labels, provenance role labels) MUST be provided through the existing pt-BR i18n catalog (and its English counterpart), with no hardcoded display strings.
- **FR-010**: The feature MUST be UI-only — it MUST NOT change the stored response format, the reconciliation derivation, the database schema, or any pipeline/CLI behavior.

### Key Entities *(include if feature involves data)*

- **Typed transcription record**: a per-page stored JSON object carrying a `doc_type` discriminator and a per-type nested structure (e.g. NFS-e: `prestador`, `tomador`, `valores`, `retencoes`; DANFE: `emitente`, `totais`, `itens`). Read-only input to the UI.
- **Reconciliation provenance**: the mapping, per document type, from a reconciliation role (total, issuer, document number, etc.) to the transcribed source field path it is derived from (e.g. NFS-e total ← `valores.valor_liquido`). Mirrors the deterministic Python mapper.
- **Legacy flat record**: a per-page stored JSON object with no `doc_type` and the pre-typed reconciliation keys. Rendered by the unchanged existing flat view.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Opening the analysis dialog on a typed transcription of any of the five known document types shows the full transcription grouped by that type's structure with localized labels, and every non-empty transcribed value is visible.
- **SC-002**: For each of the five known document types, the reconciliation total and issuer fields are visibly marked with a provenance label that matches the source field the deterministic mapper uses for that type.
- **SC-003**: Opening the dialog on a legacy flat record produces the identical rendering it produced before this feature (no visual regression).
- **SC-004**: A typed record of an unknown/`outro` type, or a partial/malformed typed record, renders all available content without dropping fields and without any runtime error.
- **SC-005**: The project's lint, format, and test suites (`pnpm lint`, `pnpm format`, `pnpm test`) pass with the change.

## Assumptions

- **A1**: The provenance the UI highlights is derived from the same rules as `scripts/analysis/type_mappers.py` (feature 053). Since the UI is TypeScript and the mapper is Python, the provenance map is mirrored in TypeScript (as the reconciliation tolerance is mirrored elsewhere in this repo) and kept as a single TS definition consumed by the renderer; the doc-type → field-path mapping is small and stable (six corpus types). The UI does not re-run the mapper; it only labels source fields.
- **A2**: "Reconciliation fields" to highlight are at minimum the reconciliation **total** and **issuer** (name/cnpj); document number, date, and service description are also marked where the mapper derives them, but the total and issuer are the load-bearing ones for SC-002.
- **A3**: The generic fallback rendering reuses the existing flatten-to-rows approach already present in the dialog (feature 055), so `outro`/unknown types and malformed shapes never crash.
- **A4**: This is the entry-detail dialog (`AttachmentAnalysisDetailDialog`); no other surface renders per-page typed transcriptions, so no other component changes.
- **A5**: Verification uses the existing e2e seed/local data; if the seeded synthetic data contains no typed transcription, a typed fixture is exercised via component-level/unit tests of the renderer and provenance map rather than blocking on seeded data.
