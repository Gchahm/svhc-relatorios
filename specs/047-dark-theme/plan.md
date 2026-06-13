# Implementation Plan: Dark theme — switchable light/dark/system mode

**Branch**: `047-dark-theme` | **Date**: 2026-06-13 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/047-dark-theme/spec.md`

## Summary

Wire a real, user-controllable theme into an already-dark-ready foundation. The Tailwind config already sets `darkMode: ["class"]`, `globals.css` already defines a full `.dark { … }` CSS-variable palette, and shadcn primitives already ship `dark:` variants — but nothing applies the `.dark` class. This feature adds `next-themes` as the runtime that toggles `.dark` on `<html>` (light / dark / system, default system, persisted to `localStorage`, no flash), a localized sun/moon theme toggle in the dashboard shell header, and a hardcoded-color audit that routes straggler colors (structural grays, semantic status hues) to the theme tokens / `dark:` variants so every surface — list pages, detail pages, dialogs, badges, header, and the auth pages — stays legible in dark mode. Labels come from the I18N-001 catalog (`Tema` / `Claro` / `Escuro` / `Sistema`).

## Technical Context

**Language/Version**: TypeScript 5 / React 19 / Next.js 15 (App Router)
**Primary Dependencies**: `next-themes` (NEW, the one added npm dep); existing — shadcn/ui (new-york), Tailwind CSS 3 (`darkMode: ["class"]` already set), lucide-react (`Sun`/`Moon`/`Monitor` icons), Radix `DropdownMenu` (already used by the user menu), the I18N-001 catalog + `useTranslation` hook (`@/lib/i18n/client`).
**Storage**: Browser `localStorage` (next-themes default). No D1, no R2, no API route, no server-side state.
**Testing**: Node built-in `node:test`/`node:assert` (the existing TS test runner, feature 045) for the catalog-completeness check that the new `theme.*` keys must pass; manual UI verification via the `ui-login` / `verify` skills against the local Miniflare D1 (prod-like data).
**Target Platform**: Cloudflare Workers via OpenNext; modern browsers.
**Project Type**: Web (Next.js App Router) — single app under `src/`.
**Performance Goals**: No measurable runtime cost; theme resolution happens before first paint via the next-themes inline script (no flash).
**Constraints**: No flash-of-wrong-theme on first paint (FR-006); `suppressHydrationWarning` on `<html>` to avoid the hydration mismatch from the pre-paint class injection (A7). No new D1 schema/migration. pt-BR labels only.
**Scale/Scope**: ~18 client surfaces flagged by the hardcoded-color scan (list/detail pages, dialogs, badges, shell, user menu), plus 2 auth pages to confirm. One provider, one toggle component, ~6 catalog keys.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- **I. Type Safety & Schema Discipline** — PASS. Pure TS; `next-themes` ships its own types. No `any`. No Drizzle/auth schema change (browser-local preference, A2/A8) → no `pnpm db:generate`/`pnpm auth:update` needed.
- **II. Cloudflare-Native Architecture** — PASS (N/A). No DB access; reads/writes no bindings. The theme provider is a client component layered under the existing server root layout; no `getCloudflareContext()` use, no build/runtime split concern.
- **III. Quality Gates Before Commit** — PASS. `pnpm lint` + `pnpm format` (4-space tabs, 120 width, double quotes) before commit. The spec requests the catalog-completeness check stay green (FR-011) — covered by the existing `catalog.test.mjs` type/shape, extended with the new `theme` keys; no new framework introduced.
- **IV. Security & Auth by Default** — PASS (N/A). No new routes, no data exposure. The toggle lives inside the already-auth-gated dashboard shell; the provider on the public auth pages exposes only a presentation preference.
- **V. Simplicity & Incremental Delivery** — PASS. One justified dependency (`next-themes` — the issue explicitly anticipates it; it is the standard shadcn approach and re-implementing OS-preference tracking + pre-paint flash avoidance by hand would be more code and more risk). Reuses the existing `DropdownMenu`, `Button`, lucide icons, and `cn()` — no new UI primitive. Delivered as priority-ordered slices (toggle+provider → persistence → audit → labels).

No violations → Complexity Tracking table left empty.

## Project Structure

### Documentation (this feature)

```text
specs/047-dark-theme/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/           # Phase 1 output (no API — documents the localStorage contract)
├── checklists/
│   └── requirements.md  # Spec quality checklist (from specify)
└── tasks.md             # Phase 2 output (speckit tasks)
```

### Source Code (repository root)

```text
src/
├── app/
│   ├── layout.tsx                       # MODIFY: add suppressHydrationWarning + ThemeProvider wrapper
│   ├── globals.css                      # (no change expected — .dark palette already complete)
│   └── dashboard/
│       ├── layout.tsx                   # MODIFY: mount ThemeToggle in header; replace bg-gray-200 dividers + nav-link grays with tokens
│       ├── UserMenu.tsx                 # MODIFY: text-gray-600 → token; (text-red-600 sign-out kept w/ dark variant or destructive token)
│       ├── ThemeToggle.tsx              # NEW: client component, sun/moon DropdownMenu (Light/Dark/System), i18n labels
│       ├── alerts/…, documents/…, entries/…, comparison/…, fines/…,
│       │   reports/…, scrape-runs/…, summary/…, units/…, vendors/…  # AUDIT: route straggler colors to tokens / add dark: variants
│       └── …
│   ├── sign-in/page.tsx                 # CONFIRM legible in dark (no change expected — uses tokens)
│   └── sign-up/page.tsx                 # CONFIRM legible in dark
├── components/
│   └── theme-provider.tsx               # NEW: "use client" wrapper around next-themes' ThemeProvider
└── lib/i18n/
    ├── catalog.ts                       # MODIFY: add `theme` namespace (toggle_label/light/dark/system) to CatalogShape + pt-BR + en
    └── catalog.test.mjs                 # (passes unchanged — shape-completeness asserts new keys present in both locales)
```

**Structure Decision**: Single Next.js App Router app. The provider lives in `src/components/` (shared, framework-level), the toggle in `src/app/dashboard/` next to `UserMenu.tsx` (it is shell chrome). The root `layout.tsx` (server component) wraps children in the client `ThemeProvider`; the existing `LocaleProvider` nesting is preserved so the toggle's `useTranslation` keeps working.

## Complexity Tracking

> No Constitution Check violations — table intentionally empty.

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|--------------------------------------|
| — | — | — |
