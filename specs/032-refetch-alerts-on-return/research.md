# Research: Refetch alerts list after resolve/reopen on the detail page

No NEEDS CLARIFICATION markers remained after specify. This document records the one design
decision and the rejected alternatives.

## Decision: trigger refetch on `document` `visibilitychange` (in addition to `window` `focus`)

- **Decision**: Add a `document.addEventListener("visibilitychange", …)` listener in the existing
  mount `useEffect` of `AlertsClient.tsx` that calls the existing `fetchData()` when
  `document.visibilityState === "visible"`, keeping the current `window` `focus` listener too. Add
  a `useRef`-based request token (a monotonically increasing counter) so the `.then(setData)` of an
  older in-flight request is ignored once a newer request has started (FR-005).
- **Rationale**:
  - The reported defect is in-app (same-tab) navigation back from the detail page. That navigation
    does not fire `window` `focus` (the tab never lost focus), which is why the list stayed stale.
  - In Next.js App Router, navigating back to `/dashboard/alerts` from `/dashboard/alerts/[id]`
    re-mounts the route segment's client tree, so the mount `useEffect` runs and `fetchData()` is
    called — meaning the **mount fetch already covers the primary path** in the common case. The
    `visibilitychange` listener is the robust, low-cost belt-and-suspenders for cases where the
    component instance is preserved (e.g. cached segment) and for tab-restore on the same window,
    closing the gap the issue describes without heavier machinery.
  - `visibilitychange` is the standard, dependency-free signal for "this page became active again"
    and is the issue's explicit Suggestion 1 (cheapest).
- **Alternatives considered**:
  - **Suggestion 2 — cross-page shared state / `router.refresh()` + server data, or a
    `BroadcastChannel`/`localStorage` ping**: Cleaner in theory but heavier than warranted for a
    client-only list that already owns its data via `fetch`. It would add coupling between the
    detail page and the list (or a new event channel) for no user-visible benefit beyond what the
    visibility/mount refetch already delivers. Rejected per constitution Principle V (simplicity).
  - **Do nothing but rely on mount refetch**: Risky — if Next.js preserves the list component
    instance across the back navigation (segment caching), the mount effect would not re-run and the
    list would stay stale. The `visibilitychange` listener guarantees freshness regardless.
  - **Poll on an interval**: Wasteful and laggy; rejected.

## Decision: in-flight stale-overwrite guard

- **Decision**: Track the latest request id in a `useRef`; in `fetchData`, capture the id at call
  time and only apply `setData`/`setError` if it is still the latest when the response resolves.
- **Rationale**: With multiple refetch triggers (mount, focus, visibilitychange) two requests can be
  in flight at once; without a guard a slower earlier response could clobber the newer data
  (FR-005). A request token is the minimal, dependency-free way to enforce last-write-wins.
- **Alternatives considered**: `AbortController` — also valid, but a request token is simpler here
  because the concern is purely "ignore the stale response", not cancelling network work; the
  endpoint is cheap. Either satisfies FR-005; the token is the smaller change.

## Out of scope (confirmed)

- BUG-003 (pipeline run wiping resolution state) — separate concern, untouched (spec A-003).
- No `/api/alerts` change, no schema/migration, no detail-page change.
