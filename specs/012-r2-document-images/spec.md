# Feature Specification: View Document Page Images from Object Storage

**Feature Branch**: `012-r2-document-images`
**Created**: 2026-06-09
**Status**: Draft
**Input**: User description: "lets add r2 to the project and allow users to view the document image on the UI fetching it from the bucket"

## User Scenarios & Testing *(mandatory)*

### User Story 1 - View a document's page images while reviewing its analysis (Priority: P1)

An auditor reviewing the fiscal documents opens a document's analysis detail and, alongside the
extracted fields and match badges, can see the actual scanned page image(s) of the underlying fiscal
document (Nota Fiscal, boleto, comprovante, etc.). This lets them visually confirm what the system
extracted against the real document — the core of trusting (or disputing) a flagged mismatch.

**Why this priority**: This is the whole point of the feature. Today the detail view shows only
extracted text/numbers; an auditor cannot verify a finding without leaving the tool. Showing the
source image turns every alert and match badge into something a human can independently confirm. On
its own it delivers the complete user value.

**Independent Test**: Open the document-analysis detail for a document known to have page images,
and confirm each page renders as a viewable image next to its extracted fields, and that the image
matches the document being analyzed.

**Acceptance Scenarios**:

1. **Given** a document whose pages are stored in object storage, **When** the auditor opens its
   analysis detail, **Then** the page image(s) are displayed and legible.
2. **Given** a multi-page document, **When** the auditor opens its detail, **Then** every page is
   viewable and presented in page order, each associated with its corresponding extracted page record.
3. **Given** an authenticated auditor, **When** they request a page image, **Then** the image is
   served; **Given** an unauthenticated visitor, **When** they request the same image URL directly,
   **Then** access is denied.

---

### User Story 2 - Inspect a page image closely (Priority: P2)

While viewing a page, the auditor can enlarge / open the image at full size to read fine print
(small CNPJ digits, handwritten amounts, stamp details) that is hard to see in the inline thumbnail.

**Why this priority**: Fiscal verification often hinges on small details. Inline display (P1) proves
the concept and covers most checks, but full-resolution inspection materially improves the auditor's
ability to confirm forgery/corruption findings. Independent of P1's plumbing once images render.

**Independent Test**: With a page image displayed, trigger the enlarge/full-view action and confirm
the image is shown at a larger, readable size.

**Acceptance Scenarios**:

1. **Given** a displayed page image, **When** the auditor activates the enlarge action, **Then** the
   image is shown at full resolution.
2. **Given** an enlarged image, **When** the auditor dismisses it, **Then** they return to the
   detail view without losing their place.

---

### Edge Cases

- **Image missing from storage**: A document row references pages but the image is absent from the
  bucket (never uploaded, deleted, or path mismatch). The detail view shows a clear "image
  unavailable" placeholder per page rather than a broken image or an error that blocks the rest of
  the detail.
- **Document with no pages**: A document/analysis with no associated page images shows the existing
  extracted-fields view with no image area (no empty/broken frame).
- **Unsupported / non-image artifact**: A stored page that is not a displayable image format shows
  the unavailable placeholder rather than attempting to render it.
- **Large image / slow load**: An image is large; the view shows a loading state and does not block
  rendering of the extracted fields, which remain visible while the image loads.
- **Direct URL access without a session**: Someone copies an image URL and opens it unauthenticated;
  the request is rejected.
- **Stale reference**: A page record exists in the database but the corresponding object key is not
  found; treated as "image missing" (placeholder), not a hard failure.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST provide durable object storage for fiscal-document page images,
  available to the application both in local development and in production.
- **FR-002**: The system MUST make each scraped document's page image(s) available in that storage,
  keyed so that a given document/analysis can be reliably mapped to its image object(s).
- **FR-003**: The document-analysis detail view MUST display the page image(s) for the document being
  viewed, alongside the existing extracted fields and match badges.
- **FR-004**: For a multi-page document, the view MUST display all pages in page order and associate
  each image with its corresponding extracted page record.
- **FR-005**: Page images MUST be retrievable only by authenticated users; unauthenticated requests
  for an image MUST be denied.
- **FR-006**: When an expected image is not present in storage, the view MUST show a per-page
  "image unavailable" indicator and MUST still render the rest of the document's analysis detail.
- **FR-007**: Image loading MUST NOT block display of the extracted fields; the extracted analysis
  data MUST render regardless of image availability or load latency.
- **FR-008**: Users MUST be able to view a page image at full resolution to inspect fine detail.
- **FR-009**: The mapping from a document/analysis record to its image object(s) MUST be derivable
  from data already associated with the document (e.g. its stored page references / page labels), so
  no manual linking is required per document.
- **FR-010**: The mechanism that populates object storage MUST be repeatable/idempotent — re-running
  it MUST NOT create duplicate or conflicting objects for the same page.

### Key Entities *(include if data involved)*

- **Document page image**: The scanned image of one physical page of a fiscal document. Belongs to a
  single document; has a page position/label; has an image format. Stored as one object in the bucket.
- **Document**: An analyzed fiscal document tied to one ledger entry; has an ordered set of page
  images and a set of extracted per-page records. The bridge between a UI row and its image objects.
- **Object storage bucket**: The durable store holding all page-image objects, addressed by a key
  derived from the document/page identity.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: An auditor can go from opening a document's analysis detail to seeing its source page
  image without leaving the application, in a single view.
- **SC-002**: For 100% of documents that have page images present in storage, those images are
  displayed in the detail view in correct page order.
- **SC-003**: For documents whose images are absent, 100% of detail views still fully render the
  extracted fields with a clear per-page unavailable indicator (no broken/blocked views).
- **SC-004**: 100% of image-fetch attempts by unauthenticated requesters are denied.
- **SC-005**: The same image-viewing experience works in local development and in production with no
  code differences (only configuration/data differs).
- **SC-006**: An auditor can enlarge any displayed page to read fine print they could not read in the
  inline view.

## Assumptions

- **Scope includes populating storage**: Because object storage is new to the project, this feature
  includes getting existing scraped page images into the bucket (a migration/upload step), not just
  the read/view path. Without populated objects there is nothing to view.
- **Source of images**: Page images already exist on disk from the scrape pipeline under the period
  folders (`data/scrape/<YYYY-MM>/`), named per page; these are the objects to be stored and served.
- **Object key derivation**: The object key is derived from the document's entry/page identity that
  is already persisted with the document (page references / page labels), so the UI can construct the
  key without new manual data entry.
- **Authentication reuses existing auth**: Image access is gated by the application's existing
  authenticated-dashboard session model; no new role/permission system is introduced.
- **Read-only for users**: End users only view images; uploading/replacing images is an operational
  pipeline concern, not a user-facing action in this feature.
- **Formats**: Page images are standard web-displayable raster formats (the formats the scraper
  already produces); no in-browser conversion of non-image artifacts is required.

## Dependencies

- The existing scraped page-image files on disk (produced by the scrape/analysis pipeline).
- The existing document → analysis → per-page-record data relationships used by the detail view.
- The existing authenticated dashboard / session mechanism that already protects the detail view and
  its data APIs.
