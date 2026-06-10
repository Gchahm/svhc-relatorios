# Feature Specification: Dedicated Document Detail Page

**Feature Branch**: `021-document-detail-page`  
**Created**: 2026-06-10  
**Status**: Draft  
**Input**: User description: "currently in dashboard/documents the user has to navigate to the entries page to see each entry, if a document has 10 entries attached that is very time consuming, I want to change the behavior so clicking in a document open a dedicated document page that has all the relevant details to it. Like the document image, all the entries and its details as well as all other documents (not attachments) that are linked to these entries"

## User Scenarios & Testing *(mandatory)*

### User Story 1 - View a document's full detail on one page (Priority: P1)

An auditor browsing the documents list (`/dashboard/documents`) clicks a document row. Instead of a
cramped dialog that only lists linked entries (and forces hopping to the entries page one entry at a
time), they land on a dedicated detail page for that document. The page shows everything they need to
audit the document in one place: the document's identifying header (number, issuer, type, total,
reconciliation status), the document's page image(s), and the full list of linked entries with each
entry's own details (period, date, description, amount, category/subcategory, vendor, unit).

**Why this priority**: This is the core ask. A document linked to 10 entries currently takes ~10
navigations to inspect; the dedicated page collapses that to a single view. Without it, nothing else
in this feature has a home.

**Independent Test**: From the documents list, click any document with at least one linked entry and
confirm a detail page opens showing the document header, at least one page image (when one exists),
and every linked entry with its details — without any further navigation.

**Acceptance Scenarios**:

1. **Given** the documents list, **When** the auditor clicks a document row, **Then** the app
   navigates to that document's dedicated detail page (a shareable URL) rather than opening a dialog.
2. **Given** a document detail page, **When** it loads, **Then** the document header (number, issuer
   name + CNPJ, type, total value, sum of linked entry amounts, over/within/under/unknown status) is
   shown.
3. **Given** a document detail page for a document with linked entries, **When** it loads, **Then**
   every linked entry is listed with its period, date, description, live amount, category,
   subcategory, vendor, and unit.
4. **Given** a document whose source attachment has page images, **When** the detail page loads,
   **Then** the document's page image(s) render on the page.

---

### User Story 2 - Reach related documents from the same page (Priority: P2)

While viewing a document, the auditor also wants to see the *other* real documents (not raw
attachments) that are linked to the same entries — e.g. when one entry is backed by both an invoice
and a separate boleto/receipt, or when an entry is split across documents. The detail page lists
those related documents and lets the auditor jump to any of their detail pages.

**Why this priority**: It closes the cross-referencing loop the dialog could not — discovering sibling
documents previously required leaving the documents view entirely. It builds on P1 (same page) but the
page is already useful without it.

**Independent Test**: Open the detail page for a document whose linked entries are also linked to at
least one other document, and confirm those other documents are listed (and only those — the current
document and plain attachments are excluded) and each navigates to its own detail page when clicked.

**Acceptance Scenarios**:

1. **Given** a document whose linked entries are also linked to other documents, **When** the detail
   page loads, **Then** those related documents are listed with enough identity to recognize them
   (number, issuer, type, total, status).
2. **Given** the related-documents list, **When** the auditor clicks a related document, **Then** the
   app navigates to that document's detail page.
3. **Given** a document whose linked entries have no other linked documents, **When** the detail page
   loads, **Then** the related-documents section shows an empty state and does not list the current
   document itself.

---

### User Story 3 - Drill into a specific linked entry when needed (Priority: P3)

For any single linked entry, the auditor can still jump to that entry in the entries view (with its
attachment analysis dialog) when they need the deeper per-entry attachment inspection that lives there.

**Why this priority**: Preserves the existing deep-link affordance so no capability is lost in the
redesign, but it is secondary to seeing everything inline.

**Independent Test**: From a document detail page, click an entry's "open in entries" affordance and
confirm it lands on `/dashboard/entries` focused on that entry.

**Acceptance Scenarios**:

1. **Given** a linked entry on the detail page, **When** the auditor activates its entries deep link,
   **Then** the entries view opens focused on that entry and period.

---

### Edge Cases

- **Document not found / invalid id**: navigating to a detail URL for a non-existent document shows a
  clear "not found" state, not a crash or infinite spinner.
- **Document with zero linked entries**: header still renders; the entries section shows an empty
  state; the related-documents section is empty.
- **No page image available** (source attachment has no images, or images fail to load): the page
  still renders the header, entries, and related documents; the image area shows a graceful "no image"
  state rather than blocking the rest of the page.
- **Document linked across multiple periods/attachments**: page images from each distinct source
  attachment are shown (or clearly attributed) so the auditor is not misled into thinking only one
  attachment backs the document.
- **Unauthorized / unauthenticated access**: the detail page and its data are gated to the same roles
  as the rest of the dashboard.
- **A linked entry references several source attachments**: each contributing source attachment's
  image is reachable; none is silently dropped.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The documents list MUST navigate to a dedicated, per-document detail page when a
  document row is activated, replacing the current in-list dialog as the primary way to inspect a
  document.
- **FR-002**: Each document detail page MUST be addressable by a stable, shareable URL that identifies
  the document, so a link can be bookmarked or shared and reopened directly.
- **FR-003**: The detail page MUST display the document's identity and reconciliation summary: document
  number, issuer name and CNPJ, document type, total value, the live sum of linked entry amounts, and
  the over/within/under/unknown status (using the same tolerance as the rest of the system).
- **FR-004**: The detail page MUST list every entry linked to the document, and for each entry show its
  period, date, description, live amount, category, subcategory, vendor, and unit.
- **FR-005**: The detail page MUST display the document's page image(s), sourced from the attachment(s)
  recorded as the document's provenance (the link's source attachment); when the document is backed by
  more than one distinct source attachment, each distinct source's image(s) MUST be reachable.
- **FR-006**: The detail page MUST list the *other* real documents linked to the same set of entries,
  excluding the current document and excluding plain attachments, with enough identity to recognize and
  navigate to each (number, issuer, type, total, status).
- **FR-007**: Each related document in that list MUST link to its own detail page.
- **FR-008**: Each linked entry MUST retain a deep link into the entries view focused on that entry and
  period (preserving the existing affordance).
- **FR-009**: A page-image load failure or a missing image MUST NOT prevent the header, entries, or
  related documents from rendering.
- **FR-010**: Requesting the detail page for a non-existent document MUST yield a clear "not found"
  state.
- **FR-011**: The detail page and any data it reads MUST be restricted to the same authenticated roles
  as the existing documents view (admin, member).
- **FR-012**: Entry amounts and the linked/related-document relationships MUST reflect live data
  (current entry amounts and current links), not values frozen at document-build time.

### Key Entities *(include if feature involves data)*

- **Document**: a real fiscal document (NF / NFS-e / receipt / boleto), identified globally by its
  normalized number + issuer CNPJ; carries issuer name, type, and total value. The subject of the
  detail page.
- **Linked Entry**: a ledger entry referencing the document (N:N via the document↔entry link), carrying
  its own period, date, description, amount, category/subcategory, vendor, and unit, plus the source
  attachment recorded as provenance for the link.
- **Source Attachment**: the per-entry page bundle recorded as a link's provenance; the origin of the
  document's page image(s).
- **Related Document**: another Document linked to one or more of the same entries as the subject
  document (the union of documents over the subject's linked entries, minus the subject itself).

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: An auditor can see all of a document's linked entries and their details on a single page
  with zero additional navigation, regardless of how many entries are linked (e.g. 10 entries are all
  visible on one page).
- **SC-002**: Inspecting a document with N linked entries requires 1 navigation (open the detail page)
  instead of N (one per entry), eliminating the per-entry hop the current dialog forces.
- **SC-003**: From a document's detail page, an auditor can reach any related document linked to the
  same entries in a single click.
- **SC-004**: The document's page image and identity are visible on the same page as its entries, so an
  auditor can cross-check the document against its ledger entries without leaving the page.
- **SC-005**: The detail page is reachable by a shareable URL that reopens the same document directly.

## Assumptions

- "Open a document page" means a client-navigable route within the existing dashboard (a new
  per-document page), replacing the existing detail dialog as the primary inspection surface. The
  existing list filtering/search on `/dashboard/documents` is retained.
- "The document image" means the page image(s) of the attachment(s) recorded as the document's
  provenance (the link's source attachment), reusing the existing authenticated page-image streaming
  used elsewhere in the dashboard. No new image storage or processing is introduced.
- "All other documents (not attachments) that are linked to these entries" means the set of *real
  documents* (the documents entity) reachable through the subject document's linked entries, minus the
  subject document — explicitly NOT the raw per-entry attachments.
- Status and reconciliation math reuse the existing shared tolerance; no new reconciliation rules are
  introduced.
- No database schema change is required; all needed relationships already exist (document↔entry links
  with source-attachment provenance, attachment analyses, entry/category/vendor/unit data).
- Read-only feature: it surfaces existing data and introduces no new write paths or pipeline changes.
