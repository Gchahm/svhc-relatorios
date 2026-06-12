# Tasks: Entries deep-link not-found notice

**Feature**: `037-deeplink-not-found-notice` | **Spec**: [spec.md](./spec.md) | **Plan**: [plan.md](./plan.md)

Tests are INCLUDED for the pure helper module only (the repo's `node --test` runner can cover
it; the React effect is verified manually per constitution III). Story phases are
independently deliverable; US1 alone is the MVP.

## Phase 1: Setup

- [x] T001 Confirm baseline: read `src/app/dashboard/entries/EntriesClient.tsx` (deep-link
  effect ~lines 244-263, `handlePeriodChange`, filter states) and `src/app/dashboard/entries/types.ts`
  (Entry.id is UUID string) to anchor the change. No file written in this task.

## Phase 2: Foundational (blocking prerequisites)

- [x] T002 Create the pure helper module `src/app/dashboard/entries/deepLink.ts` exporting
  `isValidEntryId(value: string): boolean` (case-insensitive canonical-UUID regex),
  `shortenEntryId(value: string): string` (first 8 chars + `…` when longer than 8), the
  `ResolveInput` interface, the `DeepLinkResolution` discriminated union, and
  `resolveDeepLink(input): DeepLinkResolution` implementing the exact decision order
  invalid → found → recovered-from-filter → not-found (per contracts/deepLink.md). No React/DOM
  imports.
- [x] T003 [P] Add unit tests `src/app/dashboard/entries/deepLink.test.mjs` (Node built-in
  `node:test`/`node:assert`, importing `./deepLink.ts`) covering the `isValidEntryId`,
  `shortenEntryId`, and `resolveDeepLink` tables in contracts/deepLink.md (valid/invalid uuids,
  found-with-active-filter, recovery requires present+filter, absent ⇒ not-found, no-recovery-loop
  property). Run `node --test "src/**/*.test.mjs"` and confirm green.

## Phase 3: User Story 1 — Clear feedback when the entry cannot be found (P1) — MVP

**Goal**: Replace the silent `idx === -1` path with a non-blocking dismissible notice.
**Independent test**: open `?period=<P>&entry=<valid-uuid-not-in-P>` → amber banner names entry
& period, list stays usable, success links still show no banner.

- [x] T004 [US1] In `EntriesClient.tsx`, add `deepLinkNotice` state typed
  `{ kind: "not-found" | "invalid"; entryId: string; period: string } | null` and import
  `resolveDeepLink`, `isValidEntryId`, `shortenEntryId` from `./deepLink`.
- [x] T005 [US1] In `EntriesClient.tsx`, rewrite the deep-link `useEffect` to call
  `resolveDeepLink({ entryId: deepLinkEntry, hasActiveFilter, presentUnfiltered, filteredIndex })`
  (compute `filteredIndex` via `filtered.findIndex`, `presentUnfiltered` via `entries.some`,
  `hasActiveFilter` from the four filter states) and branch: `found` → existing scroll/highlight +
  dialog-if-analysis; `not-found`/`invalid` → `setDeepLinkNotice(...)`. Keep the
  once-per-`(period|entry)` ref guard stamping only on terminal outcomes (found/not-found/invalid).
- [x] T006 [US1] In `EntriesClient.tsx`, render the dismissible notice banner inside the main
  content `Card` above the table: amber styling, message
  "Entry `<shortenEntryId(entryId)>` not found in `<period>` — it may have been removed or
  re-scraped, or the period may be wrong." (and an invalid-link variant), plus a lucide `X`
  dismiss button that clears `deepLinkNotice`. Ensure it does not block list controls.
- [x] T007 [US1] In `EntriesClient.tsx`, clear `deepLinkNotice` in `handlePeriodChange` (manual
  period change) so a stale notice does not linger (FR-009).

## Phase 4: User Story 2 — Recover an entry hidden by filters (P2)

**Goal**: When the entry loaded but is filtered out, clear filters and surface it instead of
reporting not-found.
**Independent test**: apply a filter that hides a known entry, open its deep-link → filters clear,
row scrolls/highlights, no banner; an absent entry with stray filters still shows the banner.

- [x] T008 [US2] In `EntriesClient.tsx`, handle the `recovered-from-filter` outcome in the
  effect: reset all four filter states (`setSelectedSubcategories([])`, `setSearch("")`,
  `setSelectedDocTypes([])`, `setSelectedDocMatchStatus([])`), and do NOT stamp the ref or strip
  the URL on this transitional outcome so the post-clear re-render (filtered changes) re-resolves
  to `found`. Confirm the decision order (data-model) makes an absent entry with stray filters
  resolve `not-found` (FR-005).
- [x] T009 [US2] In `EntriesClient.tsx`, clear `deepLinkNotice` when the user manually changes a
  filter (so a not-found notice clears once they adjust filters) — FR-009. Do not clear it on the
  programmatic recovery reset (which sets up a found re-run, not a manual change).

## Phase 5: User Story 3 — Validate param & keep refreshes clean (P3)

**Goal**: UUID-shape validation (already in `resolveDeepLink` via `invalid`) is surfaced, and
consumed `entry`/`period` params are stripped from the URL.
**Independent test**: `?entry=not-a-uuid` → invalid banner, no lookup; a resolved valid link →
params gone from URL; refresh does not re-trigger; selected period preserved.

- [x] T010 [US3] In `EntriesClient.tsx`, after a terminal outcome (found/not-found/invalid) strip
  `entry` and `period` from the URL via `window.history.replaceState(null, "", <pathname + cleaned
  search>)` (guard `typeof window !== "undefined"`), preserving the selected period in state (A4).
  Do not strip on `recovered-from-filter`.
- [x] T011 [US3] Verify the `invalid` branch (already produced by `resolveDeepLink` when
  `isValidEntryId` fails) renders the invalid-link notice variant from T006 and never scrolls or
  highlights with the junk value.

## Phase 6: Polish & Cross-Cutting

- [x] T012 Run `pnpm lint` and `pnpm format`; fix any findings. Confirm `node --test "src/**/*.test.mjs"`
  passes.
- [x] T013 Manual verification (verify / ui-login skills) against local prod-like D1: exercise
  success, not-found, filtered-out, and invalid-param paths plus the refresh-no-retrigger
  behavior; capture results for the PR body.

## Dependencies

- T001 (read) → everything.
- T002 (helper) blocks T003 (tests) and the US phases (T004-T011 import it).
- US1 (T004-T007) is the MVP and is self-contained once T002 exists.
- US2 (T008-T009) builds on the US1 effect rewrite (same effect) — sequential with US1 on the
  shared file.
- US3 (T010-T011) builds on the same effect; T010 (URL strip) depends on the terminal-outcome
  branches existing (T005).
- T012-T013 (polish) after all implementation.

Note: T004-T011 all edit the single file `EntriesClient.tsx`, so they are sequential (no [P]
across them). T002 and T003 are separate files (T003 is [P] relative to the US work but depends
on T002).

## Parallel opportunities

- T003 (test file) can be written in parallel with the US1 component edits once T002 exists
  (different file).

## Implementation strategy

MVP = Phase 1 + 2 + Phase 3 (US1): silent failure replaced by a notice. US2 (filter recovery)
and US3 (validation surfaced + URL cleanup) layer on incrementally, each independently testable.
