# Research: Entries deep-link not-found notice

No NEEDS CLARIFICATION markers survived `specify` (the candidate questions were resolved into
Assumptions A1-A6). This document records the small set of technical decisions for the design.

## Decision 1: Where the deep-link decision logic lives

- **Decision**: Extract a pure module `src/app/dashboard/entries/deepLink.ts` exporting
  `isValidEntryId(s)`, `shortenEntryId(s)`, and `resolveDeepLink({ entryId, entries, filtered })`
  returning a discriminated outcome. `EntriesClient` keeps only the React glue.
- **Rationale**: The repo's test runner (`node --test "src/**/*.test.mjs"`, Node 22 strips TS
  types) can unit-test a pure `.ts` module but not a `"use client"` React component. Isolating the
  branching keeps the effect thin and the logic verifiable. Mirrors the existing
  `src/lib/documents.ts` + `documents.test.mjs` pattern.
- **Alternatives considered**: Inline all logic in the effect (rejected — untestable, the effect
  already mixes concerns); a custom hook (rejected — overkill, the state it needs lives in the
  component already).

## Decision 2: Entry-id validation predicate

- **Decision**: Validate the `entry` param against the canonical UUID v-agnostic regex
  `^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$` (case-insensitive). Anything
  else ⇒ `invalid`.
- **Rationale**: `entries.id` is a text UUID (feature 031, confirmed in `types.ts`:
  `id: string` "persisted text UUID"). A shape check is cheap and prevents a doomed lookup with
  junk. Not validating against the loaded set (that's what `resolveDeepLink` does) — only shape.
- **Alternatives considered**: Accept any non-empty string (rejected — the issue explicitly asks
  for UUID-shape validation, FR-006); use the `crypto.randomUUID`-strict v4 variant bit-check
  (rejected — deterministic ids `det_id(...)` are UUID-shaped but not necessarily RFC-4122
  version/variant compliant, so a strict v4 check would wrongly reject real ids).

## Decision 3: Filter-recovery strategy

- **Decision**: When the entry is absent from `filtered` but present in the unfiltered `entries`
  for the loaded period, clear ALL client-side filters (subcategory, search, doc type, attachment
  status) by resetting their state. The entry then appears in `filtered` on the next render and
  the effect (re-run because `filtered` changed) finds and highlights it.
- **Rationale**: Deterministic and matches the existing `handlePeriodChange` reset behavior (A3).
  Selectively un-setting only the offending filter requires per-filter reverse-mapping (which
  subcategory hides it, whether the search term excludes it, etc.) — more code, more edge cases,
  no user benefit over a clean reset.
- **Alternatives considered**: Selective filter clearing (rejected — complexity, A3); leave
  filters and just notice "filtered out" (rejected — the issue's suggestion 2 explicitly prefers
  surfacing the entry over reporting not-found).

## Decision 4: Re-entrancy across the recovery re-render

- **Decision**: The effect's existing once-per-`(period|entry)` guard (`deepLinkHandledRef`) must
  NOT mark the deep-link consumed when it triggers a filter-recovery, or the post-clear re-run
  would early-return and never highlight. Recovery returns before stamping the ref; the subsequent
  run (filters now empty, row in `filtered`) resolves to `found`, highlights, and stamps the ref.
- **Rationale**: The effect re-runs when `filtered` changes (it's a dependency). The guard must
  fire only on a terminal outcome (`found` / `not-found` / `invalid`), not the transitional
  `recovered-from-filter`. A re-render bound is needed so recovery can't loop: it only clears
  filters when at least one filter is active, so once cleared there is nothing left to clear.
- **Alternatives considered**: A second ref for "recovery requested" (rejected — the
  "only clear when a filter is active" condition is already a natural fixed point; no extra state
  needed).

## Decision 5: Stripping the consumed URL params

- **Decision**: After a terminal outcome, strip `entry` and `period` from the URL via
  `window.history.replaceState(null, "", url.pathname + cleanedSearch)` (no Next.js navigation,
  no refetch). Selected period is already in component state, so the view is preserved (A4).
- **Rationale**: `replaceState` mutates the address bar without a navigation/render cycle, so it
  won't re-trigger `useSearchParams` reactions or refetch. A `router.replace` would push through
  Next's router and could re-render/re-run effects. Stripping prevents the refresh re-trigger
  (FR-007). Guarded by `typeof window !== "undefined"` for SSR safety (though this is a client
  component).
- **Alternatives considered**: `router.replace(pathname)` (rejected — heavier, may re-run data
  effects); leaving params (rejected — FR-007 requires the refresh not to re-trigger).

## Decision 6: Notice presentation

- **Decision**: An inline dismissible banner rendered just inside the main content `Card` (above
  the table), styled as a warning (amber) for not-found/invalid. Carries a dismiss button
  (lucide `X`). State: `deepLinkNotice: { kind: "not-found" | "invalid"; entryId; period } | null`.
  Cleared on dismiss, on manual period change (`handlePeriodChange`), and on manual filter change.
- **Rationale**: Non-blocking, in-view, dismissible (A2, FR-003). Amber matches the existing
  warning treatment used elsewhere (e.g. date-mismatch badge uses yellow/amber). Clearing on
  manual state change satisfies FR-009.
- **Alternatives considered**: A toast (rejected — repo has no toast system; would add a
  dependency/provider); a modal (rejected — blocking, violates A2).
