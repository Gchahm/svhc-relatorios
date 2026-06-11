# Feature Specification: Dedicated Alert Detail Page

**Feature Branch**: `022-alert-detail-page`  
**Created**: 2026-06-10  
**Status**: Draft  
**Input**: User description: "we should update dashboard/alerts so it has the same behavior as docs, clicking on a line goes into the alert details page where user has all the information needed about that alert and the user can resolve it there"

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Open an alert's full detail on one page (Priority: P1)

An auditor browsing the alerts list (`/dashboard/alerts`) clicks an alert row. Instead of the current
behavior (the row click immediately toggles the alert's resolved state via a browser prompt), they
land on a dedicated detail page for that alert. The page shows everything needed to understand the
alert: its title, severity, type, the period it concerns, when it was raised, its current
active/resolved status, the full (untruncated) description, any resolution notes, and the affected
entries — without the description being cut off and without leaving for another screen to read it.

**Why this priority**: This is the core ask — mirror the documents detail-page pattern for alerts.
The list truncates the title and description and offers no room for the alert's structured details, so
auditors can't fully understand an alert from the list. A dedicated page is the home for that detail.

**Independent Test**: From the alerts list, click any alert row and confirm a detail page opens (a
shareable URL) showing the alert's title, severity, type, period, created time, status, full
description, and affected entries — with no part truncated and no resolved-state change triggered by
the navigation itself.

**Acceptance Scenarios**:

1. **Given** the alerts list, **When** the auditor clicks an alert row, **Then** the app navigates to
   that alert's dedicated detail page (a shareable URL) and does NOT change the alert's resolved state.
2. **Given** an alert detail page, **When** it loads, **Then** it shows the title, severity, type,
   reference period, created time, active/resolved status, the full description, and any notes.
3. **Given** an alert whose data identifies affected entries, **When** the detail page loads, **Then**
   each affected entry is listed and links into the entries view focused on that entry and period.

---

### User Story 2 - Resolve or reopen the alert from its detail page (Priority: P1)

On the alert detail page, the auditor can mark the alert resolved (optionally recording notes) or
reopen a resolved alert. The status and notes update in place, and the change is reflected when they
return to the list.

**Why this priority**: The user explicitly wants resolution to happen on the detail page. Together with
US1 it replaces the list's click-to-toggle behavior with an explicit, deliberate action that has room
for notes — reducing accidental status flips from a stray row click.

**Independent Test**: Open an active alert's detail page, resolve it with a note, confirm it shows as
resolved with the note and a resolved timestamp; reopen it and confirm it returns to active. Return to
the list and confirm the new status is reflected.

**Acceptance Scenarios**:

1. **Given** an active alert's detail page, **When** the auditor resolves it and enters notes, **Then**
   the alert becomes resolved, the notes are saved, and a resolved timestamp is recorded.
2. **Given** a resolved alert's detail page, **When** the auditor reopens it, **Then** the alert
   returns to active and the resolved timestamp is cleared.
3. **Given** an alert was resolved/reopened on its detail page, **When** the auditor returns to the
   alerts list, **Then** the list reflects the alert's current status.
4. **Given** the alerts list, **When** the auditor clicks a row, **Then** no resolve/reopen happens
   from that click (resolution is only performed on the detail page).

---

### User Story 3 - See the alert's structured evidence and cross-links (Priority: P2)

Different alert types carry different structured evidence (e.g. an over-payment's invoice total vs.
sum of entries and the over amount; an amount/vendor/date mismatch's ledger value vs. extracted value;
a vendor-concentration percentage; a duplicate group's count). The detail page presents that evidence
in a readable form rather than as raw text, and when the alert concerns a known document it offers a
direct link to that document's detail page.

**Why this priority**: It turns the alert from a one-line summary into actionable context an auditor
can act on, and connects alerts to the document detail page built previously. Valuable but the page is
already useful for reading + resolving without it.

**Independent Test**: Open detail pages for a few different alert types (e.g. an over-payment, an
amount mismatch, a vendor-concentration alert) and confirm each shows its type-specific values
labeled readably; for an alert that references a document, confirm a working link to that document's
detail page.

**Acceptance Scenarios**:

1. **Given** an alert carrying structured evidence, **When** the detail page loads, **Then** that
   evidence is shown as labeled fields/values (not raw, unformatted text).
2. **Given** an alert that references a specific document, **When** the detail page loads, **Then** it
   shows a link to that document's detail page.
3. **Given** an alert with no structured evidence beyond the description, **When** the detail page
   loads, **Then** the page still renders cleanly without an empty/broken evidence section.

---

### Edge Cases

- **Alert not found / invalid id**: navigating to a detail URL for a non-existent alert shows a clear
  "not found" state, not a crash or infinite spinner.
- **Alert with no affected entries and no structured metadata**: the page still renders the core
  fields; the affected-entries and evidence sections show empty states.
- **Malformed metadata**: the page renders the core fields and degrades gracefully (no entry links / no
  evidence) rather than failing.
- **Resolve/reopen failure** (e.g. network/permission): the auditor sees an error and the displayed
  status does not falsely flip.
- **Unauthorized / unauthenticated access**: the detail page and its data are gated to the same roles
  as the rest of the dashboard.
- **A resolved alert reopened, or an alert resolved without notes**: both are allowed; notes are
  optional.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The alerts list MUST navigate to a dedicated, per-alert detail page when an alert row is
  activated, and that navigation MUST NOT change the alert's resolved state.
- **FR-002**: Each alert detail page MUST be addressable by a stable, shareable URL identifying the
  alert.
- **FR-003**: The detail page MUST display the alert's core fields: title, severity, type, reference
  period, created time, active/resolved status, the full (untruncated) description, the resolved
  timestamp (when resolved), and any notes.
- **FR-004**: The detail page MUST list the entries the alert concerns, and each MUST deep-link into
  the entries view focused on that entry and period (preserving the existing affordance).
- **FR-005**: The detail page MUST present the alert's type-specific structured evidence as labeled
  fields/values when present.
- **FR-006**: When an alert references a specific document, the detail page MUST link to that
  document's detail page.
- **FR-007**: The auditor MUST be able to resolve an active alert from the detail page, optionally
  recording notes, which sets the resolved status and a resolved timestamp.
- **FR-008**: The auditor MUST be able to reopen a resolved alert from the detail page, which clears
  the resolved timestamp.
- **FR-009**: The alerts list MUST reflect an alert's current status after it was changed on the detail
  page.
- **FR-010**: The alerts list MUST retain its existing filtering (severity, period, type, status) and
  active-count summary; only the row-click behavior changes (navigate instead of toggle).
- **FR-011**: Requesting the detail page for a non-existent alert MUST yield a clear "not found" state.
- **FR-012**: A resolve/reopen failure MUST surface an error and MUST NOT leave the UI showing a status
  that was not actually persisted.
- **FR-013**: The detail page and any data it reads or writes MUST be restricted to the same
  authenticated roles as the existing alerts view (admin, member).

### Key Entities *(include if feature involves data)*

- **Alert**: a raised finding with type, severity, title, description, reference period, created time,
  resolved flag + resolved timestamp, optional notes, and optional structured metadata (JSON). The
  subject of the detail page.
- **Affected Entry**: a ledger entry the alert concerns, identified from the alert's metadata
  (single entry id or an array of entry ids); the deep-link target in the entries view.
- **Referenced Document**: a real document an alert concerns (when its metadata carries a document
  identifier); the cross-link target on the document detail page.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: An auditor can read an alert's complete title and description (untruncated) and all of
  its structured evidence on a single page, without the list truncation.
- **SC-002**: Resolving or reopening an alert is a deliberate action taken on the detail page; a single
  click on a list row never changes an alert's status.
- **SC-003**: From an alert's detail page, an auditor can reach every affected entry, and any
  referenced document, in a single click.
- **SC-004**: After resolving/reopening on the detail page, the alerts list shows the updated status
  with no manual refresh required by the auditor beyond normal navigation.
- **SC-005**: The detail page is reachable by a shareable URL that reopens the same alert directly.

## Assumptions

- "Same behavior as docs" means the documents detail-page pattern from feature 021: a client-navigable
  per-item route under the dashboard, reached by clicking a list row, replacing the in-list interaction
  as the primary way to inspect (and here, resolve) the item.
- The list's current click-to-toggle-resolved (with a browser prompt for notes) is **removed**;
  resolution moves entirely to the detail page. The list keeps its filters, summary, and the status
  badges.
- "All the information needed" = the alert's stored fields plus a readable rendering of its metadata
  (affected entries, and type-specific values such as totals, mismatched ledger-vs-extracted values,
  percentages, counts), reusing the existing affected-entry deep-link logic.
- The document cross-link reuses the document detail page delivered in feature 021.
- No database schema change is required; the alert record already stores everything needed (including
  the metadata JSON), and resolve/reopen already exists as an operation.
- Read-mostly feature: the only write is the existing resolve/reopen operation, now invoked from the
  detail page.
