# Tasks: Dedicated Alert Detail Page

**Feature**: `022-alert-detail-page` | **Spec**: [spec.md](./spec.md) | **Plan**: [plan.md](./plan.md)

**Tests**: No automated tests (Constitution III — no framework configured; none requested).
Verification is manual via `quickstart.md`.

**Organization**: Grouped by user story. US1 + US2 are both P1 (read the detail; resolve there) — the
MVP. US3 (P2) adds structured evidence + cross-links.

## Path conventions

Single Next.js app; paths repo-relative under `src/`.

---

## Phase 1: Setup

- [x] T001 Add the canonical shadcn `Textarea` primitive at `src/components/ui/textarea.tsx` (the
  standard ~15-line wrapper over `<textarea>` using `cn()` and the same class tokens as
  `src/components/ui/input.tsx`). No CLI/network. Used by the resolve notes input.

---

## Phase 2: Foundational (blocking prerequisites)

**Purpose**: The shared data + helpers every story uses.

- [x] T002 Add `GET` to `src/app/api/alerts/[id]/route.ts`: auth-gate (admin/member → else 403);
  select the full alert by id (`id, type, severity, title, description, referencePeriod, createdAt,
  resolved, resolvedAt, notes, metadata`); 404 `{ error: "Alert not found" }` when absent. Also
  extend the existing `PATCH` response to include `metadata` (per `contracts/alert-patch.md`).
- [x] T003 Create `src/app/dashboard/alerts/alerts.ts`: move `affectedEntryIds(metadata)` and
  `entryHref(period, entryId)` out of `AlertsClient.tsx` into this shared module (exported), so the
  list and detail page share one implementation.
- [x] T004 Create shared badge components in `src/app/dashboard/alerts/AlertBadges.tsx` (or co-locate
  in `alerts.tsx`): `SeverityBadge` and `StatusBadge`, moved verbatim from `AlertsClient.tsx`, so both
  surfaces render identical badges.

**Checkpoint**: `GET /api/alerts/<id>` returns the documented shape; helpers/badges importable.

---

## Phase 3: User Story 1 — Open an alert's full detail on one page (Priority: P1) 🎯 MVP

**Goal**: Clicking an alert row navigates to `/dashboard/alerts/[id]`, a page showing all core fields
and the affected entries — and the click never changes resolved state.

**Independent Test**: Click an alert row; a detail page (not a toggle) opens showing title/severity/
type/period/created/status/full description/notes + affected-entry links.

- [x] T005 [US1] Create `src/app/dashboard/alerts/[id]/page.tsx`: thin server component reading the
  `id` param and rendering `<AlertDetailClient alertId={id} />` (inherits the `/dashboard` auth
  layout).
- [x] T006 [US1] Create `src/app/dashboard/alerts/[id]/AlertDetailClient.tsx`: fetch
  `/api/alerts/${alertId}`; render loading, error, and 404 "Alert not found" states; render the
  **core fields** card — title, `SeverityBadge`, `StatusBadge`, type, reference period, created time
  (format epoch ms), resolved time (when resolved), full **untruncated** description, and notes. Back
  link to `/dashboard/alerts`. Reuse the shared badges (T004).
- [x] T007 [US1] In `AlertDetailClient.tsx`, render the **affected entries** section from
  `affectedEntryIds(metadata)` (T003): each entry deep-links to `/dashboard/entries?period=<period>&
  entry=<id>`; empty state when there are none.
- [x] T008 [US1] Edit `src/app/dashboard/alerts/AlertsClient.tsx`: row click navigates to
  `/dashboard/alerts/${row.id}` (via `useRouter().push`) instead of `handleRowClick`; remove
  `handleRowClick` (the toggle + `window.prompt`) and the now-unused imports; import
  `affectedEntryIds`/`entryHref` from `./alerts` and the badges from the shared module (delete the
  local copies). Keep filters, summary, virtualized table, and the `Entries` deep-link column.

**Checkpoint**: US1 testable (quickstart steps 1–4, 10–11).

---

## Phase 4: User Story 2 — Resolve or reopen from the detail page (Priority: P1)

**Goal**: The auditor resolves (with optional notes) or reopens the alert on the detail page; the list
reflects the change on return.

**Independent Test**: Resolve an active alert with a note → shows resolved + note + timestamp; reopen →
active; the list shows the new status.

- [x] T009 [US2] In `AlertDetailClient.tsx`, add the resolve/reopen control: a primary button
  "Resolve" (when active) / "Reopen" (when resolved). When resolving, show a `Textarea` (T001) for
  optional notes (prefilled with existing notes). On click call `PATCH /api/alerts/${alertId}` with
  `{ resolved, notes }`; on success update local state from the response; on failure show an inline
  error and do NOT flip the displayed status (FR-012). Disable the button while in flight.
- [x] T010 [US2] In `AlertsClient.tsx`, re-fetch the list when the window/tab regains focus (add a
  `focus`/`visibilitychange` listener calling the existing `fetchData`) so a user returning from the
  detail page sees the updated status (FR-009). No shared cross-route state.

**Checkpoint**: US2 testable (quickstart steps 7–9).

---

## Phase 5: User Story 3 — Structured evidence & cross-links (Priority: P2)

**Goal**: Show the alert's type-specific metadata as labeled fields and link to a referenced document.

**Independent Test**: Open over-payment / amount-mismatch / vendor-concentration alerts; each shows
labeled values; the over-payment links to its document detail page.

- [x] T011 [US3] In `alerts.ts`, add `referencedDocumentId(metadata)` (→ `metadata.document_id` or
  null) and `evidenceFields(metadata)` returning `{ key, label, value }[]` for all metadata keys
  EXCEPT `entry_ids`/`entry_id` (rendered as entry links) and `document_id` (rendered as a doc link):
  friendly labels + formatting — currency for `total_value`/`sum_entries`/`over_amount`/`total`/
  `vendor_total`/`ledger_value`/`extracted_value` (when numeric), percent for `pct`/`rate_pct`, plain
  string/JSON fallback for the rest. Parse defensively (malformed → `[]`).
- [x] T012 [US3] In `AlertDetailClient.tsx`, render an **Evidence** section from `evidenceFields`
  (labeled grid; empty-state hidden when none, FR-005 edge), and — when `referencedDocumentId` is set
  — a link to `/dashboard/documents/<id>` (FR-006). For mismatch alerts (`ledger_value` +
  `extracted_value` present) present them as an explicit "ledger vs extracted" pair.

**Checkpoint**: US3 testable (quickstart steps 5–6).

---

## Phase 6: Polish & Cross-Cutting

- [x] T013 Run `pnpm lint` and `pnpm format`; fix issues. Confirm no unused imports remain in
  `AlertsClient.tsx` and no unjustified `any` (Constitution I, III).
- [x] T014 Manual verification per `specs/022-alert-detail-page/quickstart.md` (use `ui-login` /
  `verify`): all US acceptance scenarios + edge cases (not-found, no-evidence, malformed metadata,
  resolve failure, shareable URL).

---

## Dependencies & Execution Order

- **Setup (T001)** and **Foundational (T002–T004)** before the UI stories. T002/T003/T004 are
  independent files → parallelizable.
- **US1 (T005–T008)**: T005→T006→T007 ordered (same file grows). T008 edits a different file
  (`AlertsClient.tsx`) and depends on T003/T004 (shared helpers) existing.
- **US2 (T009–T010)**: T009 depends on T006 (detail shell) + T001 (textarea). T010 edits
  `AlertsClient.tsx` (sequence after T008 to avoid edit overlap).
- **US3 (T011–T012)**: T011 (helpers) then T012 (render); T012 depends on T006.
- **Polish (T013–T014)** last.

```text
T001 ─┐
T002 ─┼─→ T005 → T006 → T007 → T009 → T012
T003 ─┤            (T008 after T003/T004) → T010
T004 ─┘   T011 ─────────────────────────→ T012
                                           → T013 → T014
```

## Parallel Opportunities

- T002, T003, T004 (distinct files) can run in parallel.
- T008 and T010 both edit `AlertsClient.tsx` → sequential.
- T006, T007, T009, T012 all edit `AlertDetailClient.tsx` → sequential.

## Implementation Strategy

- **MVP = Phase 1 + 2 + US1 + US2 (T001–T010)**: a shareable alert detail page that shows everything
  and resolves/reopens there — the core ask.
- Then US3 (evidence + document cross-link), then lint/format + manual verification.
