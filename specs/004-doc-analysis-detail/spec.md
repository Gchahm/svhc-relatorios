# Feature Specification: Surface per-page document-analysis detail in the UI

**Feature Branch**: `004-doc-analysis-detail`
**Created**: 2026-06-06
**Status**: Draft
**Input**: GitHub issue #5 — "Surface per-page document-analysis detail (issuer, CNPJ, doc number, per-page records) in the UI"

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Inspect why a document analysis flags a mismatch (Priority: P1)

A fiscal reviewer scanning the Document Analyses page sees a row with a MISMATCH badge. They open
the row's detail view and read the extracted roll-up fields — issuer name, CNPJ, document number,
service description, document type, and any processing error — so they can judge whether the
flagged discrepancy is a genuine problem or an extraction artifact.

**Why this priority**: This is the core value of the feature. The list already tells the reviewer
*that* something is off; the roll-up detail is the first layer that begins to explain *what* is off.
It surfaces data the API already returns but never displays.

**Independent Test**: Open the Document Analyses page, open the detail view for any analysis, and
confirm the roll-up fields render with their stored values (or a clear empty indicator when absent).
Delivers value on its own even without the per-page breakdown.

**Acceptance Scenarios**:

1. **Given** a document analysis with a populated issuer name, CNPJ, document number, and service
   description, **When** the reviewer opens its detail view, **Then** all four fields are displayed
   with their values.
2. **Given** a document analysis where some roll-up fields are empty, **When** the reviewer opens
   its detail view, **Then** the empty fields show a clear "not extracted" indicator rather than a
   blank or broken layout.
3. **Given** a document analysis that recorded a processing error, **When** the reviewer opens its
   detail view, **Then** the error message is shown prominently.

---

### User Story 2 - Drill into the per-page breakdown of a multi-page document (Priority: P1)

The reviewer needs to understand a multi-page document (e.g. an invoice page plus a payment-proof
page). From the detail view they see one entry per analyzed page, each showing its page label, the
artifact role the analysis assigned it (invoice / nfse / boleto / payment_proof / other), the
per-page parsed values (gross / net / paid amounts and other extracted fields), and any per-page
parse error.

**Why this priority**: The per-page records are the most forensically useful output of the pipeline
and are currently exposed by no API route or UI at all. Seeing the invoice-vs-payment-proof
breakdown is exactly what lets a human confirm or dismiss a suspicion. Equal priority to Story 1
because the issue's core gap is that this data is entirely invisible.

**Independent Test**: Open the detail view for a multi-page analysis and confirm each page's record
is listed with its label, artifact role, parsed values, and parse error (when present).

**Acceptance Scenarios**:

1. **Given** an analysis with multiple per-page records, **When** the reviewer opens its detail
   view, **Then** every record is listed, each with its page label and artifact role.
2. **Given** a per-page record whose parsed values include gross, net, and/or paid amounts,
   **When** the reviewer views that record, **Then** those amounts are displayed with their labels.
3. **Given** a per-page record that failed to parse, **When** the reviewer views that record,
   **Then** the parse error is shown for that page.
4. **Given** an analysis that has no per-page records, **When** the reviewer opens its detail view,
   **Then** an empty-state message is shown for the per-page section.

---

### User Story 3 - Distinguish a reconciliation-driven mismatch from a plain amount mismatch (Priority: P2)

When an amount mismatch is driven by reconciliation against a payment artifact (the roll-up amount
came from a payment proof / boleto rather than the invoice gross), the reviewer can tell this apart
from a plain invoice-amount mismatch, so they understand how the compared amount was derived.

**Why this priority**: Adds interpretive clarity on top of the raw data from Stories 1 and 2.
Valuable but secondary — the underlying per-page values from Story 2 already let an attentive
reviewer infer this; this story makes it explicit.

**Independent Test**: Open the detail view for an analysis whose roll-up amount was derived from a
payment artifact and confirm the view indicates the amount came from reconciliation against that
artifact, distinct from analyses where the amount is the invoice value.

**Acceptance Scenarios**:

1. **Given** an analysis with a payment_proof or boleto record present, **When** the reviewer opens
   its detail view, **Then** the view indicates the roll-up amount was reconciled against a payment
   artifact.
2. **Given** an analysis with only an invoice record, **When** the reviewer opens its detail view,
   **Then** no payment-reconciliation indicator is shown.

---

### Edge Cases

- An analysis with a processing error and no per-page records: the detail view shows the error and
  an empty per-page section, without breaking.
- A per-page record whose stored parsed values are malformed or non-object: the view shows the
  raw extracted text (kept for exactly this case) and/or the parse error instead of crashing.
- A record with a null page label or page index: the view still renders the record using a stable
  fallback label.
- Many per-page records (long multi-page document): the detail view remains scrollable and usable.
- A reviewer without an allowed role requests the per-page detail: the request is rejected, same as
  the existing list route.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The Document Analyses page MUST provide a per-analysis detail view (an expandable row,
  panel, or dialog) reachable from each analysis in the list.
- **FR-002**: The detail view MUST display the roll-up fields `issuerName`, `extractedCnpj`,
  `documentNumber`, and `serviceDescription` when present, and a clear empty indicator when absent.
- **FR-003**: The detail view MUST display the roll-up `documentType` and any roll-up `error`.
- **FR-004**: The detail view MUST list all per-page analysis records for the analysis.
- **FR-005**: Each per-page record MUST show its page label, artifact role, parsed per-page values
  (including gross / net / paid amounts where present), and any parse error.
- **FR-006**: The per-page records MUST be served through an authenticated route guarded by the same
  allowed-roles policy as the existing document-analyses list route; unauthorized requests MUST be
  rejected.
- **FR-007**: The detail view MUST visually distinguish a roll-up amount that was reconciled against
  a payment artifact (payment_proof / boleto present) from a plain invoice-amount comparison.
- **FR-008**: The feature MUST NOT change detection logic, the database schema, or the scraper — it
  only exposes data already computed and stored.
- **FR-009**: The detail view MUST degrade gracefully when records, parsed values, or labels are
  missing or malformed (show raw text / parse error / fallback label rather than failing).
- **FR-010**: Existing list behavior (filters, sorting, summary badges, the three match badges) MUST
  remain functional and unchanged.

### Key Entities

- **Document Analysis (roll-up)**: The heterogeneity-aware summary of one analyzed document.
  Relevant attributes surfaced here: issuer name, extracted CNPJ, document number, service
  description, document type, extracted amount, the three match flags, and an optional error.
- **Document Analysis Record (per-page)**: One row per page per analysis kind for a given analysis.
  Attributes: analysis type, page index, page label, artifact role
  (invoice / nfse / boleto / payment_proof / other), parsed response values (gross / net / paid and
  other extracted fields), raw extracted text (kept when parsing failed), and a parse error.
  Belongs to exactly one Document Analysis.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: From the Document Analyses list, a reviewer can open the detail for any analysis and
  read its issuer, CNPJ, document number, and service description in a single interaction.
- **SC-002**: For any multi-page analysis, the reviewer can see 100% of its stored per-page records,
  each with page label, artifact role, parsed values, and parse error when present.
- **SC-003**: A reviewer can determine, for any flagged amount mismatch, whether the compared amount
  came from an invoice value or from reconciliation against a payment artifact, without leaving the
  page.
- **SC-004**: Requests for per-page detail from an unauthorized role are rejected 100% of the time,
  matching the existing list route's behavior.
- **SC-005**: No detection result, schema object, or scraper output changes as a result of this
  feature (verified by diff scope: only read/display paths added).

## Assumptions

- The detail view is read-only; reviewers do not edit or annotate analyses in this feature.
- Per-page parsed values are rendered generically from the stored response object; the view labels
  the well-known amount fields (gross / net / paid) and shows the remaining extracted fields without
  requiring schema changes when new fields appear.
- "Reconciled against a payment artifact" is determined from the presence of a payment_proof or
  boleto record among the analysis's per-page records, consistent with the pipeline's documented
  amount precedence.
- The existing list payload continues to carry the roll-up fields; the new route supplies the
  per-page records, fetched on demand when a detail view is opened.
