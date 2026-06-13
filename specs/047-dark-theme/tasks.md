# Tasks: Dark theme — switchable light/dark/system mode

**Feature**: `047-dark-theme` | **Spec**: [spec.md](./spec.md) | **Plan**: [plan.md](./plan.md)

Tests are OPTIONAL per the constitution; the only test work here is keeping the existing catalog-completeness check green (FR-011), which happens automatically by editing the typed catalog. No new test framework.

## Phase 1: Setup

- [X] T001 Add the `next-themes` dependency: `pnpm add next-themes` (commit the `package.json` + `pnpm-lock.yaml` change).

## Phase 2: Foundational (blocking prerequisites)

- [X] T002 Create the client theme provider in `src/components/theme-provider.tsx`: a `"use client"` module that re-exports next-themes' `ThemeProvider` (typed `React.ComponentProps<typeof NextThemesProvider>`).
- [X] T003 Wire the provider into `src/app/layout.tsx`: add `suppressHydrationWarning` to `<html>`, and wrap the body content in `<ThemeProvider attribute="class" defaultTheme="system" enableSystem disableTransitionOnChange>` around the existing `<LocaleProvider>` (ThemeProvider outermost). Keep the server `getLocale()` flow intact.

## Phase 3: User Story 1 — Switch between light/dark/system (Priority: P1) 🎯 MVP

**Goal**: A visible header control flips the whole app between light/dark/system, immediately, no reload.

**Independent test**: Open the dashboard, click the control, choose Dark → repaints dark; choose Light → repaints light; choose System → matches OS.

- [X] T004 [US1] Add the `theme` namespace to `src/lib/i18n/catalog.ts`: extend `CatalogShape` with `theme: { toggle_label; light; dark; system }`, and add pt-BR values ("Tema"/"Claro"/"Escuro"/"Sistema") and en values ("Theme"/"Light"/"Dark"/"System") to both locale objects.
- [X] T005 [US1] Create the toggle component `src/app/dashboard/ThemeToggle.tsx`: `"use client"`, a ghost icon `Button` (lucide `Sun`/`Moon` crossfade keyed off the `.dark` class, `sr-only` accessible name = `t("theme.toggle_label")`) as a `DropdownMenuTrigger`, with three `DropdownMenuItem`s (Light/Dark/System with `Sun`/`Moon`/`Monitor` icons) calling `setTheme(...)` from `useTheme()`; labels via `useTranslation()`; guard the active-mode checkmark behind a `mounted` flag to avoid an SSR hydration mismatch.
- [X] T006 [US1] Mount `<ThemeToggle />` in `src/app/dashboard/layout.tsx` header, between the `<nav>` and `<UserMenu>` (wrap the toggle + user menu in a small flex group if needed).

**Checkpoint**: US1 delivers a working, localized switch — the MVP.

## Phase 4: User Story 2 — Persistence & no-flash (Priority: P1)

**Goal**: The choice survives reload/navigation/return visit; no flash of the wrong theme.

**Independent test**: Choose Dark, reload → loads dark with no light flash; reopen tab → still dark; first-ever visit → system.

- [X] T007 [US2] Confirm next-themes persistence + default in `src/components/theme-provider.tsx` / `src/app/layout.tsx`: `defaultTheme="system"`, `enableSystem` (FR-005/FR-007), default `localStorage` key (FR-004), and that `suppressHydrationWarning` + the pre-paint inline script eliminate the flash (FR-006). Adjust props if the manual reload check shows a flash or wrong default. (Mostly verification of T002/T003 against the running app.)

**Checkpoint**: US1 + US2 = a fully persisted, flash-free switch.

## Phase 5: User Story 3 — Every surface legible in dark mode (Priority: P2)

**Goal**: No white-on-white/black-on-black; stragglers routed to tokens / `dark:` variants. Two-bucket policy (research Decision 5): structural grays → tokens; semantic status hues → keep hue + add `dark:` variant.

**Independent test**: With dark active, walk every list page, a detail page, dialogs, badges, the shell, and the auth pages — all legible.

- [X] T008 [US3] Shell chrome — `src/app/dashboard/layout.tsx`: replace the three `bg-gray-200` dividers with `bg-border`; nav-link `text-gray-600 hover:text-gray-900 hover:bg-gray-100` → `text-muted-foreground hover:text-foreground hover:bg-muted`.
- [X] T009 [US3] `src/app/dashboard/UserMenu.tsx`: trigger `text-gray-600` → `text-muted-foreground`; sign-out `text-red-600` → `text-red-600 dark:text-red-400` (or `text-destructive`).
- [X] T010 [P] [US3] Audit + fix `src/app/dashboard/alerts/AlertsClient.tsx`, `alerts.tsx`, and `alerts/[id]/AlertDetailClient.tsx`: severity/status colors keep hue + gain `dark:` variants; any structural gray/white/border → tokens.
- [X] T011 [P] [US3] Audit + fix `src/app/dashboard/documents/DocumentsClient.tsx`, `documents/[id]/DocumentDetailClient.tsx`, and `documents/StatusBadge.tsx`: over/within/under/unknown badge colors get `dark:` variants; structural colors → tokens.
- [X] T012 [P] [US3] Audit + fix `src/app/dashboard/entries/EntriesClient.tsx` and `entries/AttachmentAnalysisDetailDialog.tsx`: match/mismatch and +/- amount colors get `dark:` variants; dialog/structural colors → tokens.
- [X] T013 [P] [US3] Audit + fix `src/app/dashboard/comparison/ComparisonClient.tsx`, `summary/SummaryClient.tsx`, and `reports/ReportsClient.tsx`: delta/positive/negative colors get `dark:` variants; structural → tokens.
- [X] T014 [P] [US3] Audit + fix `src/app/dashboard/fines/FinesClient.tsx`, `units/UnitsClient.tsx`, `vendors/VendorsClient.tsx`, and `scrape-runs/ScrapeRunsClient.tsx`: status colors get `dark:` variants; structural → tokens.
- [X] T015 [P] [US3] `src/app/dashboard/SignOutButton.tsx`: any `text-red-*` gets a `dark:` variant (or `text-destructive`); structural → tokens.
- [X] T016 [US3] Confirm `src/app/sign-in/page.tsx` and `src/app/sign-up/page.tsx` render legibly in dark (they already use tokens — fix only if a straggler is found).

**Checkpoint**: All reachable surfaces legible in dark mode.

## Phase 6: Polish & Cross-Cutting

- [X] T017 Re-run the hardcoded-color scan (`grep -rE 'bg-white|text-black|bg-gray-[0-9]|text-gray-[0-9]|border-gray-[0-9]|#[0-9a-fA-F]{3,6}' src/app src/components`) and confirm every remaining hit is either an intentional semantic color now carrying a `dark:` variant or a non-visual match; document residue in the PR body.
- [X] T018 Run `node --test src/lib/i18n/catalog.test.mjs` (catalog completeness incl. `theme.*`), then `pnpm lint` and `pnpm format`. Fix any failures.
- [X] T019 Manual verification against the running app (ui-login + verify skills, local D1): exercise the quickstart steps (switch, reload-persist, system-follow, surface walk) and record findings for the PR body.

## Dependencies & Order

- **Setup (T001)** → **Foundational (T002–T003)** → everything else.
- **US1 (T004–T006)** depends on Foundational; T004 (catalog) before T005 (toggle uses the keys).
- **US2 (T007)** depends on Foundational (it verifies/tunes the provider) and is best checked after US1 is mountable.
- **US3 (T008–T016)** depends only on Foundational (needs the `.dark` class to actually appear, i.e. US1's provider) for meaningful testing, but the edits themselves are independent files — T010–T015 are `[P]` parallel. T008/T009 touch shell files also touched in US1 (layout.tsx), so sequence them after T006.
- **Polish (T017–T019)** last.

## Parallel Execution Example (US3)

T010, T011, T012, T013, T014, T015 touch disjoint files and can run in parallel once US1's provider is in place.

## Implementation Strategy

- **MVP = US1** (T001–T006): a working, localized, immediate switch.
- Then US2 (persistence/no-flash verification), then the US3 audit sweep, then polish.
