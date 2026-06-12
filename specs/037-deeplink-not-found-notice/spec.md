# Feature Specification: Entries deep-link not-found notice

**Feature Branch**: `037-deeplink-not-found-notice`  
**Created**: 2026-06-12  
**Status**: Draft  
**Input**: User description: "Surface a non-blocking notice on the entries deep-link when the target entry is not found in the loaded period (not-found, filtered-out, or invalid entry param), instead of failing silently"

## Context

The dashboard surfaces detection alerts (feature 018) that deep-link to an affected entry
via `?period=<YYYY-MM>&entry=<id>`. The entries page selects the period, scrolls to the
entry row, highlights it, and auto-opens its attachment-analysis detail dialog.

Today, when the deep-linked entry cannot be located in the displayed list, the page does
**nothing** — no scroll, no highlight, no message. A graceful "do nothing" path was
intentional only for the case "entry is present but has no attachment analysis" (so no
dialog opens). But "entry not present at all" falls through the same silent path by
accident, leaving the user staring at an ordinary entries list with no indication that a
deep-link was attempted or failed. This is indistinguishable from a successful link landing
on an un-highlighted row.

Real ways a user lands in the not-found state:

- the alert's stored `entry_id` points at a row that was re-scraped under a new id or was
  removed from the source portal (a stale alert / dead link);
- the `period` parameter is missing or malformed, so the page loads a different period than
  the one that contains the entry;
- active client-side filters (subcategory, search text, document type, attachment status)
  exclude the entry from the visible list even though it loaded for the period;
- the `entry` parameter is malformed (not a valid entry identifier).

## Clarifications

### Session 2026-06-12

Running unattended (no interactive answers available), so the candidate clarifications were
resolved by recording reasonable defaults in the Assumptions section rather than asking. The
decisions that would otherwise have been questions:

- Q: What counts as a valid `entry` parameter shape? → A: Canonical UUID (entries.id is a UUID
  string, feature 031); anything else is "invalid link" (A1, FR-006).
- Q: How is the not-found feedback presented? → A: Inline, dismissible, non-blocking notice in
  the entries view — not a modal or route-blocking error (A2, FR-001/FR-003).
- Q: On filter-recovery, clear which filters? → A: Clear ALL active client-side filters
  (subcategory, search, doc type, attachment status), matching the existing reset-on-period-change
  behavior (A3, FR-004).
- Q: Does cleaning the URL params change the loaded period? → A: No — selected period is preserved
  in component state; only the query string is stripped (A4, FR-007).
- Q: How is the entry id shown in the notice? → A: 8-char leading prefix + ellipsis, per the
  issue's "Entry <id…8>" phrasing (A5, FR-002).

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Clear feedback when the entry cannot be found (Priority: P1)

A user clicks "view affected entry" on an alert whose entry is no longer present in the
loaded period (re-scraped, removed, wrong period, or invalid id). Instead of silence, the
page shows a small, non-blocking notice telling them the entry could not be found and why
it might have happened, so they understand the link was attempted and did not silently
succeed.

**Why this priority**: This is the core defect — silent failure is the bug. Without any
feedback the user cannot tell a dead link from a working one. Delivers the primary value on
its own.

**Independent Test**: Navigate to `/dashboard/entries?period=<P>&entry=<non-existent-id>`
for a period that has data but not that entry; confirm a visible, dismissible notice appears
naming the entry and period, and that the rest of the list still works normally.

**Acceptance Scenarios**:

1. **Given** a period `P` is loaded with entries but none has id `X`, **When** the user
   opens `?period=P&entry=X`, **Then** a non-blocking notice appears stating the entry was
   not found in period `P` (with a plausible reason), and no row is highlighted and no dialog
   opens.
2. **Given** the notice is shown, **When** the user dismisses it or interacts with the list,
   **Then** the list remains fully usable and the notice does not block any controls.
3. **Given** a deep-link successfully locates and highlights an entry, **When** the row is
   found, **Then** no not-found notice is shown.

---

### User Story 2 - Recover an entry that is only hidden by filters (Priority: P2)

A user deep-links to an entry that DID load for the period but is hidden by an active
client-side filter (e.g. a leftover subcategory selection or search text). The page detects
that the entry exists in the period's unfiltered data and surfaces it rather than reporting
"not found", so the user reaches the entry they were sent to.

**Why this priority**: A "not found" message for an entry that is actually present (just
filtered out) is misleading and erodes trust. Distinguishing the two states is a meaningful
quality improvement, but secondary to ending the silent failure.

**Independent Test**: Load a period, apply a filter that hides a known entry, then open the
deep-link for that entry; confirm the page does not report "not found" and instead makes the
entry reachable (filters cleared so the row appears, scrolls, and highlights).

**Acceptance Scenarios**:

1. **Given** entry `X` loaded for period `P` but is excluded by an active filter, **When**
   the user opens `?period=P&entry=X`, **Then** the filters that hide it are cleared so the
   row becomes visible, and the row is scrolled to and highlighted.
2. **Given** entry `X` is genuinely absent from period `P`'s loaded data, **When** the user
   opens the deep-link, **Then** the not-found notice from User Story 1 is shown (the
   filter-recovery path does not mask a true not-found).

---

### User Story 3 - Reject a malformed entry parameter and keep refreshes clean (Priority: P3)

The `entry` parameter is validated for shape before use, so a malformed value does not run a
doomed lookup; and once a deep-link is consumed, the `entry`/`period` parameters are removed
from the address bar so a page refresh does not re-trigger the deep-link behavior (re-scroll,
re-highlight, re-notice).

**Why this priority**: Robustness and polish. Prevents a confusing re-trigger on refresh and
guards against junk parameters, but the feature delivers its core value without it.

**Independent Test**: Open `?period=P&entry=not-a-valid-id`; confirm the malformed-parameter
notice is shown and no lookup misbehaves. Then open a valid deep-link, let it resolve, and
refresh the page; confirm the deep-link behavior does NOT fire again because the parameters
were cleared from the URL.

**Acceptance Scenarios**:

1. **Given** a deep-link with a malformed `entry` value, **When** the page loads, **Then** a
   notice indicates the link was invalid and no row lookup is attempted with the junk value.
2. **Given** a deep-link has been consumed (found, not-found, or invalid), **When** the user
   refreshes the page, **Then** the deep-link does not re-trigger because the `entry`/`period`
   parameters were removed from the URL after the period selection was preserved.
3. **Given** the parameters are cleared from the URL, **When** they are removed, **Then** the
   currently selected period is preserved (clearing the params does not reset the view to a
   different period).

---

### Edge Cases

- **Period has no data at all** (empty period or a period the user has no entries for): the
  not-found notice still appears (the entry is, trivially, not present); the empty-list state
  remains visible behind/around the notice.
- **Period parameter missing** but `entry` present: the page loads its default period; if the
  entry is not in that period the not-found notice appears naming the loaded period.
- **Period parameter names a period that does not exist** (not in the available list): the
  page falls back to its existing period-selection behavior; the not-found notice names the
  period that was actually loaded.
- **Entry exists and has no attachment analysis**: unchanged from today — the row is scrolled
  to and highlighted, no dialog opens, and no not-found notice appears (this is a success, not
  a not-found).
- **The notice for a previous deep-link is showing** and the user manually changes the period
  or filters: the stale notice is cleared so it does not linger against unrelated state.
- **Long entry identifier**: the notice shows a shortened/truncated form of the id so it
  stays compact and readable.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: When a deep-link target entry is not located in the loaded period's data after
  loading completes, the system MUST show a non-blocking, dismissible notice instead of doing
  nothing silently.
- **FR-002**: The not-found notice MUST name the period that was loaded and a shortened form
  of the entry identifier, and MUST offer a plausible reason (the entry may have been removed
  or re-scraped under a new id, or the period may be wrong).
- **FR-003**: The not-found notice MUST NOT block interaction with the entries list or its
  controls (filters, sort, period selector remain usable while it is shown).
- **FR-004**: When the deep-link entry exists in the period's loaded data but is hidden by an
  active client-side filter, the system MUST make it reachable (clear the filters that hide
  it) rather than reporting it as not found, then scroll to and highlight the row.
- **FR-005**: The filter-recovery behavior MUST NOT mask a genuine not-found: an entry absent
  from the period's loaded data MUST still produce the not-found notice.
- **FR-006**: The system MUST validate the shape of the `entry` parameter before using it; a
  malformed value MUST produce an "invalid link" notice and MUST NOT trigger a row lookup with
  the malformed value.
- **FR-007**: After a deep-link is consumed (resolved to found, not-found, or invalid), the
  system MUST remove the `entry` (and the associated `period`) parameters from the URL so that
  a page refresh does not re-trigger the deep-link behavior, while preserving the
  currently-selected period view.
- **FR-008**: The successful deep-link behavior MUST be unchanged: when the entry is found it
  is scrolled to and highlighted, and its attachment-analysis dialog opens when an analysis
  exists; when found with no analysis, the row is still highlighted with no dialog and no
  not-found notice.
- **FR-009**: A shown notice MUST be cleared when it becomes stale — when the user manually
  changes the period or filters, or dismisses it.

### Key Entities *(include if feature involves data)*

- **Deep-link parameters**: the `period` (a `YYYY-MM` month) and `entry` (an entry
  identifier) read from the page URL that drive the scroll/highlight/dialog behavior.
- **Entry**: a ledger line for a period, identified by an entry id; the lookup target of the
  deep-link. Has zero or one attachment analysis.
- **Deep-link resolution outcome**: one of `found`, `recovered-from-filter`, `not-found`, or
  `invalid` — determines what (if anything) is shown to the user.

## Assumptions

- **A1**: The valid shape of an entry identifier is a UUID (the entries table types `id` as a
  UUID string — feature 031). The validation accepts the canonical UUID form; anything else is
  treated as a malformed link. (If a future id format is non-UUID, the validation predicate is
  the single point to update.)
- **A2**: "Non-blocking notice" means an inline, dismissible banner/alert rendered within the
  entries view (not a modal dialog and not a route-blocking error state). It does not steal
  focus or prevent list interaction.
- **A3**: "Filter-recovery" clears ALL active client-side filters (subcategory, search,
  document type, attachment status) when the entry is present-but-filtered, rather than
  selectively toggling only the offending filter — this is simpler, deterministic, and matches
  the existing "reset filters on period change" behavior. The recovered row is then found on
  the next render and scrolled/highlighted.
- **A4**: Clearing the URL parameters after consumption preserves the in-app selected period
  (the period selection has already been applied to component state), so the user keeps seeing
  the period they were sent to; only the query string is cleaned.
- **A5**: The entry-id short form in the notice is a leading prefix of the id (e.g. first 8
  characters) followed by an ellipsis, matching the issue's "Entry <id…8>" phrasing.
- **A6**: This is a client-side view change only — no API, schema, or alert-generation change.
  Alerts continue to emit whatever entry ids they emit; this feature only improves how the
  entries page responds when such an id cannot be resolved.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: For 100% of deep-links whose entry cannot be located in the loaded period, the
  user sees a visible notice (zero silent failures).
- **SC-002**: For a deep-link to an entry that loaded but is hidden by a filter, the entry
  becomes visible and highlighted without the user manually changing any filter — measured by
  the row being scrolled-to and highlighted after following the link.
- **SC-003**: A malformed `entry` parameter never triggers a list scroll or highlight and
  always yields the invalid-link notice.
- **SC-004**: After a deep-link resolves, refreshing the page does not re-show the notice or
  re-run the scroll/highlight (the parameters are gone from the URL), while the same period
  remains selected.
- **SC-005**: The successful-link experience (scroll, highlight, dialog) is identical to
  today's for entries that are present — no regression.
