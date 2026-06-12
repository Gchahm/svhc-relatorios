# Quickstart / Manual Verification: Refetch alerts list on return

## Prerequisites

- Local dev server running with seeded alerts data (`pnpm dev` + local D1), logged into the
  dashboard (`ui-login` skill).
- At least one Active alert exists.

## Verify the fix (User Story 1, P1)

1. Open `/dashboard/alerts`. Note an Active alert's row and the active-count summary badges.
2. Click the row to open its detail page (`/dashboard/alerts/[id]`).
3. Click **Resolve alert** (optionally add a note). Confirm the detail page shows Resolved.
4. Click **Back to alerts** (in-app navigation — do NOT switch browser tabs or reload).
5. **Expected**: the list shows that alert with a **Resolved** status badge, and the active-count
   summary badges reflect one fewer active alert. No tab switch or reload was needed.

## Verify reopen (Acceptance Scenario 2)

1. Open a Resolved alert's detail page, click **Reopen alert**.
2. Navigate back to the list.
3. **Expected**: the alert shows as **Active** again; active-count summary incremented.

## Verify the Active filter (Acceptance Scenario 3)

1. Set the **Status** filter to "Active".
2. Resolve an alert on its detail page, return to the list.
3. **Expected**: the resolved alert is no longer listed (it no longer matches Active), and other
   filter selections (severity/period/type) are preserved.

## Verify no regression (FR-003)

1. With the list open, switch to another browser tab and back.
2. **Expected**: the list still refetches on tab focus (existing behavior intact).

## Quality gates

- `pnpm lint` passes.
- `pnpm format` leaves the file unchanged (or run it to format).
