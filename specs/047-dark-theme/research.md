# Phase 0 Research: Dark theme

No `[NEEDS CLARIFICATION]` markers remained after specify/clarify; this records the technical decisions that back the plan.

## Decision 1: Theme runtime — `next-themes`

- **Decision**: Use `next-themes` `ThemeProvider` with `attribute="class"`, `defaultTheme="system"`, `enableSystem`, and its default `localStorage` storage key (`theme`).
- **Rationale**: It is the standard shadcn/ui approach (the issue mandates it), and it solves the three hard parts for free: (a) toggling the `.dark` class on `<html>` (matching the Tailwind `darkMode: ["class"]` config already present), (b) `prefers-color-scheme` tracking for system mode (FR-007), and (c) a pre-paint inline `<script>` that sets the class before first paint, eliminating the flash (FR-006). Re-implementing these by hand would be more code and more failure surface, violating Principle V less cleanly.
- **Alternatives considered**: Hand-rolled context + `useEffect` + `matchMedia` listener + manual `localStorage` — rejected: cannot avoid the first-paint flash without an inline pre-hydration script, which is exactly what next-themes ships. A cookie-based server-rendered theme — rejected: heavier (needs reading the cookie in the server layout, no account-sync requirement justifies it; A2 keeps it browser-local).

## Decision 2: Flash avoidance + hydration

- **Decision**: Add `suppressHydrationWarning` to the root `<html>` element; mount the `ThemeProvider` (client) inside the server `RootLayout`, wrapping (or wrapped by) the existing `LocaleProvider`.
- **Rationale**: next-themes mutates `<html class>`/`style` before React hydrates, so without `suppressHydrationWarning` React logs a hydration mismatch on `<html>` (A7). next-themes' own docs require exactly this. The provider must be a client component (`"use client"`) but can be nested in the server root layout via composition.
- **Provider nesting**: `ThemeProvider` wraps `LocaleProvider` (or vice-versa — order is immaterial since they are independent contexts). Chosen order: `ThemeProvider` outermost, `LocaleProvider` inside, so the whole tree (including any future non-dashboard content) is themeable while locale stays as-is. The toggle component (`useTranslation`) must therefore be inside both providers — it is (it lives in the dashboard shell, deep in the tree).

## Decision 3: Toggle control shape

- **Decision**: A compact icon `Button` (ghost, `size="sm"`/icon) showing a `Sun` icon in light and `Moon` in dark (CSS-crossfade via the shadcn pattern: `Sun` with `dark:-rotate-90 dark:scale-0`, `Moon` with `dark:rotate-0 dark:scale-100`), opening a `DropdownMenu` with three `DropdownMenuItem`s: Light / Dark / System (each with its lucide icon: `Sun`/`Moon`/`Monitor`). Placed in the header between the nav and the `UserMenu`.
- **Rationale**: Matches the adjacent `UserMenu`'s `DropdownMenu` pattern (reuse, Principle V), and makes the three explicit modes — including System — discoverable, which the acceptance criteria require (A4). Uses `useTheme()` from next-themes to read/set; reads `theme` (the chosen mode) for the active checkmark, not `resolvedTheme`.
- **Alternatives considered**: A single cycling icon button (light→dark→system) — rejected: hides the System option and the current mode, weaker discoverability.

## Decision 4: Hydration-safe toggle rendering

- **Decision**: The toggle gates its theme-dependent visual on a `mounted` flag (`useState(false)` + `useEffect(() => setMounted(true), [])`), rendering a stable placeholder (or the icon without the active-state checkmark) until mounted.
- **Rationale**: `useTheme()` returns `undefined`/`system` on the server and the resolved value only after mount; reading it during SSR/first render would cause a mismatch. The standard next-themes guard is the `mounted` flag. The icon button itself (Sun/Moon crossfade) is pure CSS keyed off the `.dark` class so it does not need the guard; only the menu's active-checkmark / current-mode logic does.

## Decision 5: Hardcoded-color audit strategy

- **Decision**: Two-bucket policy (A6):
  - **Structural grays** that stand in for theme tokens → migrate to tokens: `bg-gray-200` dividers → `bg-border`; nav-link `text-gray-600 hover:text-gray-900 hover:bg-gray-100` → `text-muted-foreground hover:text-foreground hover:bg-muted`; `UserMenu` `text-gray-600` → `text-muted-foreground`.
  - **Semantic status colors** (red/green/yellow/blue/amber for badges, severity, +/- amounts) → keep the hue, add a `dark:` variant so they stay legible on dark backgrounds (e.g. `text-red-600 dark:text-red-400`, `bg-yellow-100 text-yellow-800 dark:bg-yellow-900/40 dark:text-yellow-300`). Destructive sign-out can stay a red token (`text-destructive`) or `text-red-600 dark:text-red-400`.
- **Rationale**: Tokens already flip with the palette, so structural chrome needs no per-element dark variant. Semantic colors carry meaning (over/under, severity) that must survive the theme; dark-50…-400 shades read on dark, light-600…-800 read on light. The scan found ~18 files; the affected token set is small and well-understood (see plan's count).
- **Out of scope**: Chart palettes (`--chart-1..5` already have dark values); no palette redesign.

## Decision 6: i18n keys

- **Decision**: Add a `theme` namespace to `CatalogShape`: `theme.toggle_label` ("Tema"), `theme.light` ("Claro"), `theme.dark` ("Escuro"), `theme.system` ("Sistema"); plus the same keys in the optional `en` catalog ("Theme"/"Light"/"Dark"/"System").
- **Rationale**: The catalog is a typed nested dict where every key in `CatalogShape` must exist in both locales; `catalog.test.mjs` enforces shape-completeness. Adding to the type forces both locale objects to define them (compile-time + test-time). Labels are read via `useTranslation()` in the client toggle.
- **Alternatives considered**: Inline literals — rejected (FR-010 forbids raw English; consistency with #64).
