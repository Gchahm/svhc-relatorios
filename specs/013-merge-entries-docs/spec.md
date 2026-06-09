# Feature Specification: Merge Document Analyses into the Entries page

**Feature Branch**: `013-merge-entries-docs`  
**Created**: 2026-06-09  
**Status**: Draft  
**Input**: User description: "we currently have a page dashboard/document-analyses and dashboard/entries but we could merge them into the same page since each entry of document analysis is based of an entry from entries"

## Overview

Today the dashboard has two separate places that describe the same underlying thing:

- **Entries** — the period's financial ledger (every revenue/expense line), with a period selector, category filter, search, sort, and revenue/expense/net totals.
- **Document Analyses** — a separate global list (all periods at once) where each row is the result of analysing a fiscal document, joined back to the **entry** it belongs to. It shows the entry amount vs. the extracted document amount, amount/vendor/date match badges, document-type and match-status filters, and a click-through detail dialog with page images.

Because every document analysis is derived from exactly one entry, the two lists are two views of the same rows. This feature folds the document-analysis information **into** the Entries page so an auditor sees, in one place, each ledger line and — where a fiscal document was analysed for it — whether that document matches the books.

## Clarifications

### Session 2026-06-09

- Q: How should the merged page be scoped (Entries is period-scoped; Document Analyses is global)? → A: Period-scoped — keep the Entries period selector; document data follows the period's entries; cross-period hunting via switching periods.
- Q: How should an entry's document-analysis status be surfaced in the merged list? → A: Inline match badges (amount/vendor/date + doc-type) on entries that have an analysis, with click-to-open the existing detail dialog; entries without a document stay plain rows.
- Q: What happens to the old `/dashboard/document-analyses` route and its "Docs" nav link? → A: Redirect the old route to the merged Entries page and remove the separate nav link.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - See document-match status alongside each entry (Priority: P1)

An auditor opens the Entries page for a period and, for every entry that has an analysed fiscal document, sees at a glance whether the document's amount, vendor, and date match the entry — without leaving the page or cross-referencing a second screen.

**Why this priority**: This is the core of the merge — surfacing analysis status next to the entry it describes. It alone delivers the value of having one unified view.

**Independent Test**: Open the merged Entries page for a period that contains analysed documents; confirm entries with an analysis display amount/vendor/date match indicators (and a document-type indicator) inline, while entries without an analysed document display as plain ledger rows.

**Acceptance Scenarios**:

1. **Given** a period with entries that have analysed documents, **When** the auditor views the Entries page, **Then** each such entry shows amount-match, vendor-match, and date-match indicators reflecting the latest analysis for that entry.
2. **Given** an entry with no analysed document, **When** the auditor views the page, **Then** that entry appears as a normal ledger row with no match indicators (a neutral/empty state, not a "mismatch").
3. **Given** an entry whose document analysis recorded a processing error, **When** the auditor views the page, **Then** the entry is marked as having an analysis error distinct from a clean match and from a mismatch.

---

### User Story 2 - Open the full document detail from an entry (Priority: P1)

From an entry that has an analysed document, the auditor opens the existing rich detail view (extracted fields and the document's page images) to investigate a discrepancy.

**Why this priority**: The detail dialog with page images is the investigative payoff of the analysis; the merge must preserve it. Without it the inline badges have no drill-down.

**Independent Test**: On the merged page, click an entry that has an analysis; confirm the document detail dialog opens with the same extracted fields and page-image viewing available on the standalone page today.

**Acceptance Scenarios**:

1. **Given** an entry with an analysed document, **When** the auditor activates that row, **Then** the document-analysis detail dialog opens showing the extracted fields and the document's page images.
2. **Given** an entry with no analysed document, **When** the auditor activates that row, **Then** no document-detail dialog opens (the row has no document to inspect).
3. **Given** the detail dialog is open, **When** the auditor closes it, **Then** they return to the same period view with their filters and scroll position intact.

---

### User Story 3 - Find entries with document discrepancies for a period (Priority: P2)

An auditor narrows the period's entries to only those whose document disagrees with the books (amount/vendor/date mismatch or analysis error), and can also narrow by document type, to focus an investigation.

**Why this priority**: Filtering to discrepancies is how the standalone page is actually used for fraud/error hunting; preserving it keeps the merged page useful for audits, but it builds on the P1 surfacing.

**Independent Test**: On the merged page, apply a "has document mismatch" filter and confirm the list reduces to entries whose analysis shows at least one mismatch or an error; apply a document-type filter and confirm the list reduces accordingly.

**Acceptance Scenarios**:

1. **Given** a period with a mix of matching and mismatching documents, **When** the auditor filters to "has mismatch", **Then** only entries with at least one of amount/vendor/date mismatch (or an error) remain.
2. **Given** the auditor filters by a document type, **When** the filter is applied, **Then** only entries whose analysed document is of that type remain.
3. **Given** document filters are active, **When** the auditor combines them with the existing search and category filters, **Then** all active filters apply together (logical AND).
4. **Given** the auditor switches the selected period, **When** the new period loads, **Then** the document filters reset along with the existing entry filters (consistent with current period-change behaviour).

---

### User Story 4 - Reach the merged view from old links (Priority: P3)

A user who follows an existing bookmark or link to the old Document Analyses page lands on the merged Entries view instead of a dead page, and the duplicate top-nav item is gone.

**Why this priority**: Cleanup and link-preservation; it has no value until the merged page exists, but it prevents broken links and removes the now-redundant navigation.

**Independent Test**: Navigate to the old `/dashboard/document-analyses` URL and confirm it lands on the merged Entries page; confirm the top navigation no longer shows a separate "Docs" item.

**Acceptance Scenarios**:

1. **Given** the merged page exists, **When** a user opens the old document-analyses URL, **Then** they are taken to the merged Entries page.
2. **Given** the merge is complete, **When** a user views the dashboard navigation, **Then** there is a single entry point to the entries/documents view and no separate document-analyses item.

---

### Edge Cases

- **Entry with multiple analyses / multiple document pages**: an entry's row reflects a single roll-up match status; the detail dialog shows all of that entry's pages (current behaviour). The merge MUST NOT regress multi-page documents.
- **Shared-NF / split entries**: several entries can derive from one shared document. Each participating entry independently shows its own match status (the analysis is fanned out to siblings today); the merge preserves per-entry status and does not collapse siblings into one row.
- **Period with zero analysed documents**: the page behaves exactly like today's Entries page (no document columns populated; no error).
- **Analysis exists but extracted amount is absent**: the document-amount value shows as empty, and the amount-match indicator reflects "unknown" rather than "mismatch".
- **Revenue vs. expense entries**: revenue entries typically have no fiscal document; they remain plain rows and are not flagged.
- **Large period**: the merged list MUST remain responsive (the list is virtualised today); adding document columns must not break smooth scrolling.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The Entries page MUST be the single, period-scoped home for both ledger entries and their document-analysis status.
- **FR-002**: For each entry that has at least one document analysis in the selected period, the page MUST display, inline with the entry, indicators for amount match, vendor match, and date match, plus an indication of the document type.
- **FR-003**: An entry that has no associated document analysis MUST display as a normal ledger row with a neutral/empty document state (explicitly distinct from a "mismatch").
- **FR-004**: An entry whose latest analysis recorded a processing error MUST be visibly distinguished from both a clean match and a value mismatch.
- **FR-005**: Activating an entry that has an associated document analysis MUST open the existing document-analysis detail view, showing the extracted fields and the document's page images.
- **FR-006**: Activating an entry that has no associated document analysis MUST NOT open a document-detail view.
- **FR-007**: Users MUST be able to filter the period's entries to those whose document analysis shows at least one mismatch or an error ("has discrepancy"), and to those with all checks matching.
- **FR-008**: Users MUST be able to filter the period's entries by analysed document type.
- **FR-009**: The new document filters MUST combine (logical AND) with the existing entry search and category filters, and MUST reset when the selected period changes, consistent with current behaviour.
- **FR-010**: The page MUST show a period-level summary of document-analysis health (e.g., counts of amount/vendor/date mismatches and analysis errors among the period's analysed entries) so an auditor sees the period's document status without scrolling the list.
- **FR-011**: The existing Entries capabilities — period selection, category/subcategory filtering, description search, column sorting, and revenue/expense/net totals — MUST be preserved.
- **FR-012**: The document-analysis data shown MUST be scoped to the selected period (it follows the period's entries), not the global all-periods list shown today.
- **FR-013**: The old document-analyses route MUST redirect to the merged Entries page so existing links continue to work.
- **FR-014**: The dashboard navigation MUST present a single entry point to this view; the separate "Docs"/document-analyses navigation item MUST be removed.
- **FR-015**: No fiscal data, analysis records, or document images may be altered, deleted, or re-analysed by this change; it is a presentation/navigation change only (read-only over existing data).

### Key Entities *(include if feature involves data)*

- **Entry**: one financial ledger line for a period (date, description, amount, movement type C/D, category/subcategory, vendor, unit). The organising unit of the merged page.
- **Document Analysis**: the result of analysing one entry's fiscal document — document type, extracted amount/vendor (CNPJ + issuer)/date, the amount/vendor/date match flags against the entry, an optional processing error, and references to the document's page images. Belongs to exactly one entry (via its document); an entry's row reflects one rolled-up analysis status.
- **Match status**: the per-entry roll-up of amount/vendor/date checks plus error state, surfaced inline on the entry and used by the discrepancy filter and the period summary.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: An auditor can determine, for any entry in a period, whether its fiscal document matches the books without navigating to a second page (100% of analysis status available on the Entries page).
- **SC-002**: Every entry that has an analysed document exposes the full document detail (fields + page images) in one interaction (a single click/activation).
- **SC-003**: The separate Document Analyses navigation item is removed and the merged view is reachable from exactly one navigation entry point.
- **SC-004**: Following the old document-analyses link lands the user on the merged view 100% of the time (no dead page).
- **SC-005**: For a period, the count of entries flagged with a document discrepancy on the merged page equals the count of mismatching/errored analyses for that period under the previous standalone page (no findings lost or invented by the merge).
- **SC-006**: The merged list remains smoothly scrollable for the largest existing period (no perceptible degradation versus today's Entries page).

## Assumptions

- The merged page is **period-scoped** (it keeps the Entries period selector); cross-period mismatch hunting is done by switching periods. The previous global "all periods at once" document view is intentionally not reproduced.
- Document-analysis status is surfaced as **inline badges + click-to-detail** on entry rows; entries without a document remain plain rows.
- The old `/dashboard/document-analyses` route is **redirected** (not removed) to preserve existing links, and its separate nav item is dropped.
- "Latest analysis for an entry" is the existing per-entry roll-up already used by the standalone page; no new reconciliation logic is introduced.
- This is a read-only presentation/navigation change over existing D1 data; no schema, scraper, or analysis-pipeline changes.
