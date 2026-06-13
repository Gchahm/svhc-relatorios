# Feature Specification: Vision Extraction Provenance on Document & Alert Detail

**Feature Branch**: `048-doc-vision-provenance`
**Created**: 2026-06-13
**Status**: Draft
**Input**: User description: "https://github.com/Gchahm/svhc-relatorios/issues/81 — Surface the vision extraction object on document & alert detail so reviewers can audit how total_value was derived"

## User Scenarios & Testing *(mandatory)*

A reviewer auditing the condominium's fiscal data opens a document and sees a total figure (e.g. **R$800,00**) that the system derived automatically from the AI reading of the attached invoice pages. When that figure disagrees with what the reviewer reads on the page image (e.g. the invoice visibly shows **R$320,00**), the reviewer currently has no way to tell *why* the system arrived at its number — was it an AI misread, a multi-page invoice, the wrong field picked, or a genuine discrepancy? This feature makes the AI extraction that produced the figure visible and traceable from the document and alert review surfaces, so a reviewer can resolve the question without leaving the app.

### User Story 1 - See the AI extraction behind a document's total (Priority: P1)

A reviewer on a document detail page wants to understand where the document's total figure came from. They open the AI extraction for the relevant attachment and see, per page, exactly what the AI read (the gross, net, and paid amounts, issuer, date, document number, the page's role such as invoice/boleto/payment proof) alongside the page image.

**Why this priority**: This is the core of the request — without it, a reviewer cannot distinguish an AI artifact from a real finding, which is the whole purpose of the auditing tool. It is independently valuable even if nothing else ships.

**Independent Test**: Open a document whose total was derived from an AI extraction; trigger the extraction view; confirm the per-page extracted values and page images are shown and match the underlying analysis.

**Acceptance Scenarios**:

1. **Given** a document detail page for a document linked to at least one analyzed attachment, **When** the reviewer activates the "view AI extraction" control, **Then** the AI extraction object opens showing the roll-up summary plus each page's extracted fields next to its page image.
2. **Given** a document whose total visibly disagrees with the page image, **When** the reviewer opens the extraction, **Then** they can see the per-page extracted amounts and identify which value the system read.

---

### User Story 2 - Trace the total to the exact extracted field (Priority: P1)

A reviewer wants the document's headline total to state, in plain language, **which page and which extracted field** produced it (or that it fell back to a roll-up estimate), so the number is self-explaining rather than a mystery.

**Why this priority**: Seeing the full extraction (Story 1) helps, but the reviewer still has to guess which value became the total. An explicit attribution closes the loop on the "why R$800?" question directly and is the difference between "inspectable" and "obvious."

**Independent Test**: For a document whose total was taken from a specific page's gross amount, confirm the UI names that page and field; for a document with no confident gross, confirm the UI indicates the fallback source.

**Acceptance Scenarios**:

1. **Given** a document whose total was set from a page's extracted gross amount, **When** the reviewer views the document header, **Then** a provenance line names the source page and field (e.g. "from page p3, invoice gross").
2. **Given** a document whose total came from the roll-up fallback (no confident gross on any page), **When** the reviewer views the header, **Then** the provenance line indicates the fallback source rather than a specific page field.
3. **Given** a document with no extractable total at all, **When** the reviewer views the header, **Then** the status reads "unknown" and the provenance line states no AI total could be derived.
4. The page/field the UI attributes the total to MUST match the value the pipeline actually used to compute the total (no divergence between the explanation and the computation).

---

### User Story 3 - Reach the same extraction from an alert (Priority: P2)

A reviewer reading an alert that was triggered by a document or attachment total (e.g. an over-payment or an amount-mismatch alert) wants to reach the same AI extraction object and see that the disputed figure originates from an AI reading, so the alert is understood in context.

**Why this priority**: The document surface (Stories 1–2) is the primary entry point; the alert surface reinforces the same transparency for the reviewer who arrives via an alert. The extraction view already partly exists on alert detail, so this is reinforcement and labelling rather than net-new capability.

**Independent Test**: Open an alert driven by a total-based check; confirm the AI extraction for the implicated attachment is reachable and that the alert's referenced figure is labelled as AI-extracted.

**Acceptance Scenarios**:

1. **Given** an alert whose finding depends on a document/attachment total, **When** the reviewer opens the alert detail, **Then** they can reach the AI extraction object for the implicated attachment.
2. **Given** such an alert, **When** the reviewer views the figure the alert is based on, **Then** the UI conveys that the figure was produced by AI extraction (so the reviewer knows to verify it against the page).

---

### Edge Cases

- **Document has no analyzed attachment** (e.g. the linking attachment was never classified): the extraction control is absent or disabled with a clear reason; no error.
- **Analysis exists but every page failed to parse / has errors**: the extraction view opens and surfaces the parse errors per page rather than appearing empty.
- **Total came from the roll-up fallback, not a page gross**: provenance attribution names the fallback, never a fabricated page/field.
- **Multiple analyses contribute (same invoice across periods)**: the total reflects the highest confident figure; the provenance points to the analysis/page that supplied it, not an arbitrary one.
- **A page image is missing or unviewable in storage**: the extracted fields still display; the image area shows an unavailable state, consistent with existing behavior.
- **Language**: all new labels appear in the app's default language (pt-BR), not raw English.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The document detail surface MUST provide a control that opens the AI extraction object for an attachment linked to the document, showing the roll-up summary and each page's extracted fields alongside the page image. It MUST reuse the existing extraction-detail presentation rather than introduce a divergent one.
- **FR-002**: The document header MUST display a provenance attribution for the document's total: the source page and extracted field when the total came from a page-level gross amount, or an explicit fallback indication when it came from the roll-up estimate, or a "no AI total derived" indication when none exists.
- **FR-003**: The provenance attribution shown in the UI MUST be consistent with how the pipeline computes the total (prefer the first confident gross across pages, else the roll-up amount). The selection rule MUST have a single shared source of truth so the UI explanation and the computed value cannot drift.
- **FR-004**: When a document's status indicates a discrepancy (the total disagrees with the linked entries — over / under / unknown), the reviewer MUST be able to reach the per-page extracted values and page image within one interaction, so the cause is inspectable.
- **FR-005**: Alert detail surfaces for alerts driven by a document or attachment total MUST make the same AI extraction object reachable for the implicated attachment, and MUST label the disputed figure as AI-extracted.
- **FR-006**: When a document has no analyzed attachment (no extraction to show), the system MUST present this clearly (control absent or disabled with a reason) and MUST NOT error.
- **FR-007**: When an extraction exists but pages have parse errors or missing values, the system MUST display the available extracted fields and surface the errors, rather than showing an empty or misleading view.
- **FR-008**: All new user-facing text MUST be presented in the application's default language (pt-BR) via the existing localization mechanism; no raw English literals.

### Key Entities *(include if feature involves data)*

- **Document**: the de-duplicated real fiscal document identified by its number + issuer; carries the headline **total** figure under audit and a status relative to its linked entries. The subject the reviewer is inspecting.
- **AI Extraction (attachment analysis)**: the object the vision model produced for an attachment — a roll-up summary plus one record per page. Each page record carries the extracted amounts (gross, net, paid), issuer, date, document number, service description, the page's artifact role, and any parse error. This is what the feature surfaces.
- **Total provenance**: the derived attribution stating which page + extracted field (or fallback) supplied the document's total. Not stored separately; computed from the extraction using the same rule the pipeline uses.
- **Alert**: a finding that may reference a document/attachment total; the secondary entry point from which the reviewer reaches the extraction.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: From a document detail page, a reviewer can open the AI extraction and see the per-page extracted values and page image in a single interaction (one control activation), with no separate navigation step.
- **SC-002**: For any document with a derived total, the reviewer can read, on the document page, which page and field (or fallback) produced the total — verifiable by comparing the displayed attribution to the value the pipeline used.
- **SC-003**: Given a document whose total disagrees with its page image, a reviewer can determine whether the figure is an AI artifact or a genuine discrepancy without leaving the application.
- **SC-004**: A reviewer arriving via a total-driven alert can reach the same AI extraction and recognizes the disputed figure as AI-extracted.
- **SC-005**: All new labels render in pt-BR; no raw English appears on the affected surfaces.

## Assumptions

- The routing key from a document to its AI extraction is already available on the document detail data (the linked attachment's analysis id is already exposed), so no new data linkage is required.
- The extraction-detail presentation already used on the alert surface is the canonical view to reuse on the document surface.
- The total-selection rule (prefer first confident gross, else roll-up) is the existing pipeline behavior and is the rule the UI attribution must mirror; a shared client-side helper already mirrors the tolerance math and is the natural home for the selection rule.
- No database schema change, migration, pipeline change, or new third-party dependency is required; this is a presentation-layer feature reading existing data.
- "Total-driven alert" means an alert whose finding is based on a document or attachment total (e.g. over-payment, amount-mismatch); alerts unrelated to totals are out of scope for FR-005.
