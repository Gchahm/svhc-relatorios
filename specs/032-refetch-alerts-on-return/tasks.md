# Tasks: Refetch alerts list after a resolve/reopen action on the detail page

**Feature**: 032-refetch-alerts-on-return | **Spec**: [spec.md](./spec.md) | **Plan**: [plan.md](./plan.md)

This is a single-file client-side fix. Tests are OPTIONAL (constitution Principle III — no test
framework) and none were requested in the spec, so verification is manual (quickstart.md).

## Phase 1: Setup

- [X] T001 Confirm the working tree is on branch `032-refetch-alerts-on-return` and clean; ensure `pnpm` deps are installed (`pnpm install` if needed) so `pnpm lint`/`pnpm dev` run.

## Phase 2: Foundational

_No foundational/blocking prerequisites — the change is confined to one existing client component and reuses the existing `/api/alerts` flow._

## Phase 3: User Story 1 — Resolved alert appears resolved on return to the list (P1)

**Goal**: After resolve/reopen on the detail page, the list reflects the new status on the next
same-tab return without a tab switch or reload (FR-001, FR-002).

**Independent test**: Resolve an Active alert on its detail page, click "Back to alerts", confirm
the row shows Resolved and the active-count summary decremented — no tab switch / reload.

- [X] T002 [US1] In `src/app/dashboard/alerts/AlertsClient.tsx`, add a `document` `visibilitychange` listener (alongside the existing `window` `focus` listener) inside the mount `useEffect` that calls `fetchData()` when `document.visibilityState === "visible"`; register and clean up both listeners in the same effect (FR-001, FR-002, FR-003).
- [X] T003 [US1] In `src/app/dashboard/alerts/AlertsClient.tsx`, add a `useRef` request-token guard so an older in-flight `/api/alerts` response cannot overwrite a newer one: increment the token at the start of `fetchData`, capture it, and apply `setData`/`setError`/`setLoading` only when the captured token is still the latest (FR-005). Keep filter state untouched (FR-004).

## Phase 4: User Story 2 — List stays current after any same-tab navigation (P3)

**Goal**: Returning from any in-app navigation refreshes the list, not only the resolve path.

**Independent test**: Navigate from the list to another dashboard page and back via in-app links;
the list shows current data.

- [X] T004 [US2] Verify (no code beyond T002 needed) that the `visibilitychange` + mount refetch in `src/app/dashboard/alerts/AlertsClient.tsx` covers return from any same-tab in-app navigation — confirm during manual verification per `specs/032-refetch-alerts-on-return/quickstart.md`. (US2 is satisfied by the US1 mechanism; this task is the explicit confirmation, not new code.)

## Phase 5: Polish & Cross-Cutting

- [X] T005 Run `pnpm lint` and `pnpm format`; fix any issues so the change passes the quality gates (constitution Principle III).
- [X] T006 Manually verify all scenarios in `specs/032-refetch-alerts-on-return/quickstart.md` against the running app (resolve → back shows Resolved; reopen → back shows Active; Active filter hides a just-resolved alert; tab-focus refetch still works). Record results for the PR body.

## Dependencies

- T001 (setup) → T002, T003 (US1 implementation) → T004 (US2 confirmation) → T005 (gates) → T006 (verify).
- T002 and T003 touch the same file (`AlertsClient.tsx`) so they are NOT parallel; do them in order.

## Implementation Strategy

MVP = Phase 3 (US1). It alone fixes the reported defect and is independently testable. US2 (Phase 4)
adds no code — it is confirmation that the same mechanism generalizes. Polish (Phase 5) is the gate +
manual verification required before the PR.
