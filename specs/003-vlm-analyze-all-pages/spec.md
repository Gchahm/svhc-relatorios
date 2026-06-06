# Feature Specification: Vision-analyze every page of a document, with per-page parsed results

**Feature Branch**: `003-vlm-analyze-all-pages`  
**Created**: 2026-06-05  
**Status**: Draft  
**Input**: User description: "Vision-analyze every page of a document, with per-page parsed results"

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Analyze every page of a multi-page document (Priority: P1)

An auditor runs the document-analysis pass over a scraped fiscal period. For each
fiscal entry's document — which may be a single physical document made of several
page images — the system visually inspects **every** page, not just the first.
Content that only appears on a later page (e.g. a payment proof on page 4) is no
longer invisible to the analysis.

**Why this priority**: This is the core defect. Today only page 1 is analyzed, so
any mismatch, alteration, or forgery on later pages is silently missed — directly
undermining the fraud/forgery-detection goal. Fixing this is the minimum viable
slice and everything else builds on it.

**Independent Test**: Run the analysis pass on a period containing a known
multi-page document and confirm the document's analysis reflects content found on
a page after the first (a value that appears only on a later page shows up in the
document-level summary).

**Acceptance Scenarios**:

1. **Given** a document whose page-image list contains 4 pages, **When** the
   analysis pass runs, **Then** all 4 pages are visually analyzed (one analysis
   pass per page) and the document-level summary is derived from content across
   all 4 pages.
2. **Given** a single-page document, **When** the analysis pass runs, **Then** the
   document is analyzed exactly as before, producing one page-level result.

---

### User Story 2 - Preserve each page's parsed result as its own record (Priority: P1)

For each document, the system records what each page produced as a separate,
structured per-page record linked back to the document, instead of storing only
the first page's raw text as an opaque string. Each per-page record captures which
page it came from, the kind of analysis performed, the artifact role of that page,
and the page's parsed values (or the raw text / error if parsing failed).

**Why this priority**: Without per-page records there is nowhere to keep the
later-page content that Story 1 now reads, and the existing single raw-text field
cannot represent heterogeneous multi-page documents. This is required for Story 1
to deliver durable value and for later analysis kinds to attach their own results.

**Independent Test**: After analyzing a 3-page document, confirm exactly 3 per-page
records exist, each linked to the one document analysis, each carrying its page
reference and parsed values; analyzing a single-page document produces exactly 1
record.

**Acceptance Scenarios**:

1. **Given** a 3-page document, **When** analysis runs, **Then** exactly one
   document-level analysis object is produced plus 3 per-page records linked to it,
   and the document is **not** split into 3 document-level objects.
2. **Given** a page whose image fails to parse into structured values, **When**
   analysis runs, **Then** a per-page record is still written for that page
   containing its raw text and/or an error indication, and the rest of the
   document's pages continue to be analyzed.
3. **Given** an already-analyzed document, **When** a different kind of analysis is
   added later, **Then** new records can be attached to the same document
   (distinguished by their analysis-kind label) without altering or colliding with
   the existing page-extraction records, and the model permits more than one record
   per page.

---

### User Story 3 - Heterogeneity-aware document roll-up (no false mismatch) (Priority: P1)

The document-level summary fields and the entry validations (amount / vendor /
date matches) are derived from the whole document, accounting for the fact that one
document can bundle different artifact types (e.g. an invoice, a bank slip, and a
payment proof) carrying legitimately different values. When a payment artifact is
present, the amount match is validated against the amount actually paid (the
invoice net), not the invoice gross — eliminating false mismatches.

**Why this priority**: The page-1-only behavior currently emits false mismatches
(reading an invoice's gross value while the money actually moved at the net value
on a later page). A correct roll-up is the user-visible payoff of analyzing all
pages; without it, Stories 1–2 produce better data but the headline audit signal
is still wrong.

**Independent Test**: Re-run the analysis on the known heterogeneous evidence
document and confirm its document-level amount match flips from a false mismatch to
a correct match, while both the invoice gross and net and the paid amount remain
recoverable from the per-page records.

**Acceptance Scenarios**:

1. **Given** the evidence document (entry `b27329f0-b020-56fc-b4b9-a38943a49c4d`,
   period `2025-12`, entry amount R$ 61.590,43) whose pages are NFS-e invoice (×2),
   a boleto, and a payment proof, **When** analysis runs, **Then** each page's
   record is tagged with its artifact role, the gross (74.791,04), net (61.590,43)
   and paid (61.590,43) values are all preserved across the per-page records, and
   the document-level amount match is **true** (validated against the paid/net
   value), not the current false mismatch against the gross.
2. **Given** a document where the invoice gross differs from the net due to
   retentions, **When** analysis runs, **Then** the document-level summary does not
   erase the gross/net distinction — both remain recoverable from the per-page
   records.

---

### User Story 4 - Per-page records survive import into the audit database (Priority: P2)

When analysis results are imported into the audit database, each per-page record is
created as its own row linked to its document analysis, and each record's structured
values round-trip back to their original structure with no corruption.

**Why this priority**: The per-page records are only useful downstream if they
import faithfully. A latent defect in the importer serializes any structured value
to a corrupt literal placeholder, silently destroying the column; this story
guarantees the data the earlier stories produce is actually usable in the database.

**Independent Test**: Import a period that has per-page records and confirm the
records exist as linked rows and that a record's structured response read back from
the database matches the original structure (no `"[object Object]"`-style
corruption).

**Acceptance Scenarios**:

1. **Given** analysis output containing per-page records with structured values,
   **When** it is imported, **Then** each record becomes a row linked to its
   document analysis and its structured response deserializes back to the original
   structure.
2. **Given** any field whose value is a structured object or list, **When** it is
   imported, **Then** it is serialized faithfully rather than collapsing to a
   placeholder string.

---

### Edge Cases

- **Single-page document**: behaves as today, producing exactly one page-extraction
  record.
- **Missing/unreadable page file**: that page is skipped for analysis but a failure
  record is still written for it; the document as a whole is not aborted and its
  other pages are analyzed.
- **Unparseable page response**: a record is still written with the raw text and/or
  an error; the document is not aborted.
- **Mixed image extensions** within one document's page list (e.g. `.jpg` and
  `.png`) are all handled.
- **Page ordering**: each per-page record's page reference aligns to the page's
  position / filename page-suffix in the document's page list.
- **Document with no payment artifact** (invoice only): amount match falls back to
  the best available representative value, with no payment artifact to prefer.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The document-analysis pass MUST analyze every page image listed for a
  document, performing one visual analysis per page image, rather than only the
  first page.
- **FR-002**: The system MUST continue to produce exactly one document-level
  analysis object per document; it MUST NOT split a multi-page document into
  multiple document-level objects.
- **FR-003**: For each page analyzed, the system MUST emit a separate per-page
  analysis record linked to its parent document analysis. A document with N pages
  yields N page-extraction records.
- **FR-004**: Each per-page record MUST carry: a reference to its parent document
  analysis; an analysis-kind label identifying the type of analysis (e.g.
  page-extraction) distinct from any prompt text; a page reference aligned to the
  page's position / filename page-suffix in the document's page list; the artifact
  role/type of that page as classified during analysis (e.g. invoice/NFS-e, boleto,
  payment proof, other); and the page's parsed/structured values — or the raw text
  and/or an error when parsing failed.
- **FR-005**: The per-page record model MUST allow multiple records per document and
  more than one record per page, so additional analysis kinds can be added later —
  for an already-analyzed document — without schema changes and without colliding
  with or altering existing page-extraction records.
- **FR-006**: When a page's image is missing/unreadable or its response cannot be
  parsed, the system MUST still write a per-page record for that page (raw text
  and/or error) and MUST NOT abort analysis of the document's remaining pages.
- **FR-007**: The document-level summary fields (document type, extracted amount,
  extracted issuer identifier, issuer name, extracted date, document number, service
  description) and the entry validations (amount / vendor / date matches, preserving
  existing tolerances) MUST be derived from content across all pages, not only the
  first page.
- **FR-008**: The roll-up MUST NOT assume a single representative value for a
  document. When a payment artifact (boleto or payment proof) is present, the amount
  match MUST be validated against the amount actually paid / the invoice net, not
  the invoice gross.
- **FR-009**: When an invoice's gross and net differ due to retentions, the
  document-level summary MUST NOT erase the distinction; both values MUST remain
  recoverable from the per-page records.
- **FR-010**: Per-page detail MUST live in the per-page records; the document-level
  fields are a best-effort summary for quick scanning, not the source of truth for
  cross-artifact comparison. The legacy single raw-response string MUST no longer be
  used to carry per-page detail.
- **FR-011**: On import into the audit database, each per-page record MUST be
  created as its own row linked to its document analysis, and each record's
  structured response MUST round-trip back to its original structure.
- **FR-012**: The import process MUST serialize structured (object/list) values
  faithfully rather than collapsing them to a placeholder string, for the per-page
  response and for any other structured field.

### Key Entities *(include if feature involves data)*

- **Document analysis**: One record per physical document for a fiscal entry. Holds
  the document-level roll-up summary (document type, extracted amount, issuer
  identifier and name, date, document number, service description) and the entry
  validations (amount/vendor/date match). Parent of one or more per-page analysis
  records.
- **Per-page analysis record**: A normalized record linked to a document analysis.
  Attributes: parent document-analysis reference; analysis-kind label; page
  reference; artifact role/type; structured response (with raw text and/or error
  when parsing failed). Multiple records may exist per document and per page,
  distinguished by analysis-kind label.
- **Fiscal entry**: The scraped period entry (amount, vendor, date) that a document
  is validated against. Unchanged by this feature except that its validations are
  now derived from all pages.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: For a multi-page document, 100% of its page images are visually
  analyzed (a document with N page images yields N page-extraction records).
- **SC-002**: A value that appears only on a page after the first is reflected in
  the document-level summary, demonstrating the summary is derived from beyond page
  1.
- **SC-003**: Single-page documents continue to produce exactly one page-extraction
  record (no regression).
- **SC-004**: For the known heterogeneous evidence document, the document-level
  amount match changes from a false mismatch to a correct match, and the invoice
  gross, invoice net, and paid amount are all recoverable from its per-page records.
- **SC-005**: After import, 100% of per-page records' structured responses
  deserialize back to their original structure (zero corrupted/placeholder values).
- **SC-006**: A new analysis kind can be attached to an already-analyzed document
  without altering existing page-extraction records and without a schema change.
- **SC-007**: A document containing a missing/unreadable page or an unparseable page
  still completes analysis for its remaining pages and records a failure entry for
  the affected page (zero aborted documents from a single bad page).

## Assumptions

- The analysis tool processes one image per visual-analysis call; multi-page
  handling is achieved by iterating pages, not by a single multi-image call.
- The per-page records are nested under their document analysis in the intermediate
  scraped-period output and normalized into their own table on import.
- The per-page structured response is stored serialized as text in a single column;
  whether the legacy document-level raw-response column is dropped or retained as
  unused legacy is a planning/implementation decision, not a scope question.
- Existing match tolerances for amount/vendor/date are preserved as-is.
- Artifact roles classified in this feature are at least: invoice/NFS-e, boleto,
  payment proof, and other.

## Out of Scope

- The scraper's document collection/extraction and the one-document-per-entry schema
  constraint (covered by a separate ticket).
- Implementing any analysis kind other than page-extraction (e.g. forgery
  detection) — this feature only emits page-extraction records plus the reusable
  model future kinds build on.
- Full cross-artifact reconciliation (the invoice gross − retentions = net → boleto
  → payment proof → entry chain across artifact types) — a later phase with its own
  ticket. This feature only classifies each page's artifact role and preserves each
  artifact's values so reconciliation is possible later, plus the heterogeneity-aware
  amount-match rule above.
