# Implementation Plan: Entries deep-link not-found notice

**Branch**: `037-deeplink-not-found-notice` | **Date**: 2026-06-12 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/037-deeplink-not-found-notice/spec.md`

## Summary

The entries page (`src/app/dashboard/entries/EntriesClient.tsx`) responds to an alert
deep-link `?period=<YYYY-MM>&entry=<id>` by scrolling to and highlighting the entry row and
opening its attachment-analysis dialog. When the entry can't be located in the loaded list,
the effect silently does nothing. This feature replaces that silent failure with explicit,
non-blocking feedback: (1) a dismissible inline notice when the entry is genuinely absent or
the link is invalid, (2) automatic filter-recovery when the entry loaded for the period but is
hidden by an active client-side filter, and (3) validation of the `entry` param shape plus
stripping the consumed `entry`/`period` params from the URL so a refresh doesn't re-trigger.

Technical approach: extend the existing single deep-link `useEffect`. The resolution is a small
pure decision over `(deepLinkEntry, validity, entries (unfiltered), filtered)` yielding one of
`found` / `recovered-from-filter` / `not-found` / `invalid`. The decision logic is factored into
a pure, unit-testable helper (`resolveDeepLink`) so it can be tested without React; the effect
applies the outcome (scroll/highlight/dialog, clear filters, or set a notice state) and then
strips the URL params via `window.history.replaceState` (no navigation). A new dismissible
notice element renders above the list. No API, schema, or server change.

## Technical Context

**Language/Version**: TypeScript 5 / React 19 / Next.js 15 (App Router, client component)
**Primary Dependencies**: Existing only — React (`useEffect`/`useRef`/`useState`/`useMemo`),
`next/navigation` (`useSearchParams`), shadcn/ui (`Button` for dismiss), lucide-react (icon),
`@tanstack/react-virtual` (existing virtualizer). No new dependency.
**Storage**: N/A — client-side view change; reads no new data, writes nothing.
**Testing**: Repo has no JS test framework configured (constitution III — tests OPTIONAL). The
pure `resolveDeepLink` helper is structured for testability; manual verification via the running
app (verify / ui-login skills) against local prod-like D1 data is the gate for this UX change.
**Target Platform**: Cloudflare Workers (OpenNext) — browser-rendered client component.
**Project Type**: Web application (Next.js single app).
**Performance Goals**: No measurable impact — the resolution runs once per consumed deep-link.
**Constraints**: Must not block list interaction (non-blocking notice); must not regress the
existing successful-link / no-analysis behavior; UUID-shape validation for the `entry` param.
**Scale/Scope**: One client component file (`EntriesClient.tsx`) plus a small pure helper
module; optionally a co-located unit test for the helper.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- **I. Type Safety & Schema Discipline**: PASS. TypeScript only, no `any`; the deep-link outcome
  is a discriminated string union typed explicitly. No schema/migration change (no persisted
  data touched), so Drizzle/auth-schema rules are not engaged.
- **II. Cloudflare-Native Architecture**: PASS. No DB access added; no `getCloudflareContext`
  use; purely client-side. `window.history.replaceState` is a standard browser API used in a
  `"use client"` component (no SSR path).
- **III. Quality Gates Before Commit**: PASS (committed to). `pnpm lint` + `pnpm format` run
  before commit. A unit test for the pure helper is added (allowed, not mandated). Manual app
  verification accompanies this user-facing change.
- **IV. Security & Auth by Default**: PASS. The entries page is already auth-gated; this change
  adds no route and exposes no new data. The `entry` param is validated (UUID shape) before use.
- **V. Simplicity & Incremental Delivery**: PASS. Extends one existing effect; the three user
  stories are independently shippable (US1 alone is a viable MVP). No new abstraction beyond one
  pure helper extracted for testability/clarity.

No violations — Complexity Tracking left empty.

## Project Structure

### Documentation (this feature)

```text
specs/037-deeplink-not-found-notice/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/           # Phase 1 output (the resolveDeepLink contract)
├── checklists/
│   └── requirements.md  # from specify
└── tasks.md             # Phase 2 output (speckit tasks)
```

### Source Code (repository root)

```text
src/app/dashboard/entries/
├── EntriesClient.tsx        # MODIFIED — deep-link effect: outcome handling, notice UI,
│                            #   filter-recovery, param validation, URL param stripping
└── deepLink.ts              # NEW — pure helpers: isValidEntryId(), shortenEntryId(),
                             #   resolveDeepLink() (the discriminated-outcome decision)

src/app/dashboard/entries/
└── deepLink.test.ts         # NEW (optional, allowed) — unit tests for resolveDeepLink/helpers
```

**Structure Decision**: Web application (single Next.js app). The change is localized to the
existing `entries` dashboard route folder. The decision logic is extracted into a sibling pure
module `deepLink.ts` so it carries no React/DOM dependency and is unit-testable; `EntriesClient`
imports it and owns only the React glue (state, effect, JSX notice). This keeps the effect thin
and the testable logic isolated, satisfying Principle V.

## Complexity Tracking

> No constitution violations — section intentionally empty.
