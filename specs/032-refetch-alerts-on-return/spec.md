# Feature Specification: Refetch alerts list after a resolve/reopen action on the detail page

**Feature Branch**: `032-refetch-alerts-on-return`
**Created**: 2026-06-12
**Status**: Draft
**Input**: User description: "IMP-009: Alerts list shows stale resolved state after resolving on the detail page; refetch alerts list after resolve action on detail page"

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Resolved alert appears resolved on return to the list (Priority: P1)

An auditor opens the alerts list, clicks an Active alert to open its detail page, resolves it (optionally adding a note), then uses in-app back navigation to return to the list. The list immediately reflects the alert as Resolved — its status badge shows Resolved and the Active/Resolved filter and the active-count summary badges are consistent — without the user having to switch browser tabs or hard-refresh.

**Why this priority**: This is the entire defect. The resolve workflow added in feature 022 appears not to have taken effect because the list still shows the alert as Active after in-app navigation back (no `window.focus` event fires on same-tab navigation). It directly undercuts the user's confidence that their action succeeded.

**Independent Test**: Resolve an alert on its detail page, navigate back to the list with the in-app "Back to alerts" link, and confirm the alert's status badge reads Resolved and the active-count summary decremented — all without switching tabs or reloading.

**Acceptance Scenarios**:

1. **Given** an Active alert visible in the list, **When** the user opens its detail page, resolves it, and clicks "Back to alerts", **Then** the list shows that alert with a Resolved status badge and the active-count summary badges reflect one fewer active alert of that severity.
2. **Given** a Resolved alert, **When** the user opens its detail page, reopens it, and navigates back to the list, **Then** the list shows that alert with an Active status badge and the active-count summary badges reflect one more active alert.
3. **Given** the Status filter is set to "Active", **When** the user resolves an alert on its detail page and returns to the list, **Then** the resolved alert is no longer shown (it no longer matches the Active filter).

---

### User Story 2 - List stays current after returning from any same-tab navigation (Priority: P3)

When the user returns to the alerts list from any in-app navigation (not only after resolving), the list shows current data, so a status change made elsewhere is never silently stale.

**Why this priority**: A general robustness improvement; the P1 story already covers the reported defect. This story just ensures the refresh mechanism is not narrowly coupled to the resolve action.

**Independent Test**: Navigate away from the list to any other dashboard page and back via in-app links; confirm the list reflects the latest alert states.

**Acceptance Scenarios**:

1. **Given** the user navigated away from the alerts list and an alert's state changed, **When** the user navigates back to the list in the same tab, **Then** the list shows the current state.

---

### Edge Cases

- The user resolves an alert, returns to the list, and the refetch fails (network/server error): the list must not blank out or show a confusing empty state — it should surface the error consistent with the existing error handling.
- The user navigates back before the in-flight refetch completes: the most recent navigation's data must win (no stale response overwriting newer data).
- The list is already showing the correct data (e.g. browser back from a page where nothing changed): a redundant refetch is acceptable and must not cause flicker that disrupts scroll position or selected filters.
- Existing behavior on returning to a different browser tab (the `window` focus refetch) must continue to work.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The alerts list MUST refresh its data when the user returns to the list page via in-app (same-tab) navigation, including the back navigation from an alert's detail page.
- **FR-002**: After a resolve or reopen action on the detail page, the list MUST reflect the new status — the per-row status badge, the Active/Resolved filter results, and the active-count summary badges — on the next return to the list, without requiring a browser tab switch or a hard refresh.
- **FR-003**: The list MUST preserve the existing refresh-on-tab-focus behavior (returning from another browser tab still refreshes).
- **FR-004**: The refresh MUST NOT discard the user's current filter selections (severity, period, type, status).
- **FR-005**: A refresh that is in flight when a newer one starts MUST NOT let the older response overwrite the newer data (no stale overwrite).
- **FR-006**: When a refresh fails, the list MUST surface the failure consistent with the existing error handling.

### Key Entities *(include if feature involves data)*

- **Alert**: A finding surfaced by the pipeline, with a status (Active/Resolved). The list shows many alerts; the detail page shows one and lets the user change its status. The list's rendered status must stay in sync with changes made on the detail page across in-app navigation.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: After resolving an alert on the detail page and returning to the list via the in-app back link, the alert shows as Resolved in 100% of attempts, with zero manual tab switches or page reloads required.
- **SC-002**: The active-count summary badges and the Active/Resolved filter results agree with the per-row status badges after the return — no row shows a status that contradicts the summary or filter.
- **SC-003**: The existing tab-focus refresh and all current filters continue to work unchanged (no regression).

## Assumptions

- **A-001**: The fix is a client-side data-freshness change on the alerts list page; no API, schema, or pipeline change is required (the `/api/alerts` endpoint already returns current status).
- **A-002**: "In-app navigation back" is the primary trigger to cover (the reported path). The cheapest viable mechanism (per the issue's Suggestion 1) is to also refresh when the page becomes visible/active again on the same tab — in addition to the existing tab-`focus` listener — rather than introducing cross-page shared state or a broadcast channel (Suggestion 2), which is heavier than warranted for this defect.
- **A-003**: BUG-003 (resolution state wiped by the next pipeline run) is a separate, out-of-scope concern noted in the issue's Suggestion 3; this feature only fixes the UI freshness gap and does not touch the pipeline's writeback of resolution state.
- **A-004**: A redundant refetch on return (when nothing changed) is acceptable; the list is small and the endpoint is cheap. Avoiding flicker / preserving filters is required (FR-004), but de-duplicating no-op fetches is not.
