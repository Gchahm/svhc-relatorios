# Implementation Plan: I18N-001 Localization Foundation

**Branch**: `039-i18n-foundation` | **Date**: 2026-06-12 | **Spec**: `specs/039-i18n-foundation/spec.md`  
**Input**: Feature specification from `/specs/039-i18n-foundation/spec.md`

## Summary

Build a foundation for application-wide localization by introducing a typed message catalog (pt-BR canonical, en optional), server and client locale resolution, and centralized formatting helpers. Wire the sign-in page and dashboard navigation as reference examples. This feature unblocks I18N-002 (locale persistence), I18N-003 (regional number/currency formatting), and I18N-004 (dynamic locale switching).

## Technical Context

**Language/Version**: TypeScript 5, React 19, Next.js 15 (App Router)  
**Primary Dependencies**: No new dependencies; homegrown typed-dictionary module (`src/lib/i18n/`)  
**Storage**: N/A — presentation-layer only, no schema changes  
**Testing**: Node.js `node:test` + `.test.mjs` pattern for catalog completeness (existing pattern)  
**Target Platform**: Cloudflare Workers via OpenNext  
**Project Type**: Web (Next.js 15 / TypeScript)  
**Performance Goals**: Locale resolution must be <1ms; no additional bundle cost beyond the message catalog  
**Constraints**: Must work on Cloudflare Workers Edge Runtime (no Node.js-only APIs); single-tenant, internal tool  
**Scale/Scope**: ~200 UI strings to localize (estimated from dashboard components); ~40 alert types

## Constitution Check

**Gate**: Must pass before Phase 1 design. Re-check after implementation.

- **I. Type Safety & Schema Discipline**: ✅ PASS — Message catalog will be a typed TypeScript module with strict key validation via generics. Catalog keys are validated at build/test time; missing keys cause TypeScript errors.
- **II. Cloudflare-Native Architecture**: ✅ PASS — Locale resolution uses no Node-only APIs. Server components read locale from Cloudflare context (or defaults); client components use React context. No external bindings required.
- **III. Quality Gates Before Commit**: ✅ PASS — All code passes `pnpm lint` and `pnpm format`. Unit test for catalog completeness runs in CI.
- **IV. Security & Auth by Default**: ✅ PASS — No security implications; presentation-layer only. Auth is out of scope.
- **V. Simplicity & Incremental Delivery**: ✅ PASS — Homegrown typed-dictionary approach (no new dependencies) is simpler than `next-intl`. Single feature branch delivers a complete, independently testable foundation.

**Status**: ✅ All principles satisfied. No deviations.

## Project Structure

### Documentation (this feature)

```text
specs/039-i18n-foundation/
├── spec.md                  # Feature specification
├── plan.md                  # This file
├── research.md              # Phase 0 output (research tasks)
├── data-model.md            # Phase 1 output (entities & relationships)
├── contracts/               # Phase 1 output (API contracts if applicable)
├── quickstart.md            # Phase 1 output (getting started guide)
└── tasks.md                 # Phase 2 output (task breakdown)
```

### Source Code (repository root)

```text
src/
├── app/
│   ├── layout.tsx           # Root layout: update <html lang> attribute
│   ├── (auth)/
│   │   └── sign-in/
│   │       └── page.tsx     # Sign-in page: localized (reference example)
│   └── dashboard/
│       ├── layout.tsx       # Dashboard layout: nav bar (reference example)
│       ├── entries/
│       ├── documents/
│       └── alerts/
│
├── lib/
│   ├── i18n/                # NEW: i18n module
│   │   ├── index.ts         # Exports: getLocale(), t(), getCatalog()
│   │   ├── catalog.ts       # Message catalog (typed dictionary)
│   │   ├── server.ts        # Server-side locale resolution
│   │   ├── client.tsx       # Client context & hooks
│   │   └── formatters.ts    # Centralized formatting helpers (currency, date, percent, number)
│   │
│   ├── alerts.ts            # Update: ALERT_TYPE_LABELS → use t() from i18n
│   └── r2.ts                # (unchanged)
│
└── components/
    └── (existing components refactored to use i18n/t())
        # E.g., Dashboard, EntriesClient, AlertsClient, etc.

tests/
└── i18n/
    └── catalog.test.mjs     # Unit test: catalog completeness
```

**Structure Decision**: Single Next.js 15 project with a new `src/lib/i18n/` module. No new projects or major refactors. All localization logic lives in `src/lib/i18n/`; components import from it as needed.

## Design Approach

### Phase 0: Research (Completed in-spec)

**Resolved unknowns:**
- **Typed catalog structure**: Use a nested object dictionary with TypeScript generics to enforce type safety. Keys are strings; catalog is a readonly object with `as const`. Locale is a union type of supported locales.
- **Server vs. client locale**: Server components use `getLocale()` (returns locale from Cloudflare context or defaults to `"pt-BR"`). Client components use `LocaleProvider` (React context) seeded at layout render time.
- **Formatters**: Centralize all `toLocaleString()` calls into `formatCurrency()`, `formatDate()`, `formatPercent()`, `formatNumber()` functions in `src/lib/i18n/formatters.ts`. All derive locale from `getLocale()` or context.
- **Alert type labels**: Import `ALERT_TYPE_LABELS` from the catalog (not a static object); map machine keys to localized labels.

### Phase 1: Design & Contracts

#### 1.1 Data Model (`data-model.md`)

**Message Catalog Entity:**
- **Structure**: `Catalog = { [locale: string]: { [path: string]: string } }`
- **Keys**: Hierarchical paths (e.g., `"nav.home"`, `"button.submit"`, `"alert.attachment_amount_mismatch"`)
- **Values**: Localized strings
- **Constraints**: Every key in `pt-BR` is canonical; en keys are optional. Missing keys in en fall back to pt-BR at runtime.
- **Lifecycle**: Static, baked into the build artifact. No runtime mutations.

**Locale Entity:**
- **Type**: `"pt-BR" | "en"`
- **Default**: `"pt-BR"`
- **Resolution**: Server reads from Cloudflare context or request headers; client reads from context.
- **Persistence**: Not in scope for this foundation (I18N-002 will add cookies).

#### 1.2 API Contracts (`contracts/`)

**No new API endpoints** for this foundation feature. All changes are client/server-side rendering and catalog lookups. Future features (I18N-002) may add endpoints for locale preferences.

#### 1.3 Quickstart (`quickstart.md`)

**For developers adding new strings:**

```typescript
// 1. Add to catalog in src/lib/i18n/catalog.ts:
export const catalog = {
  pt_BR: {
    nav: { home: "Início", settings: "Configurações" },
    button: { submit: "Enviar", cancel: "Cancelar" },
  },
  en: { ... }
};

// 2. In a server component:
import { t } from "@/lib/i18n";
export default function Header() {
  return <h1>{t("nav.home")}</h1>;
}

// 3. In a client component:
"use client";
import { useTranslation } from "@/lib/i18n/client";
export function Button() {
  const t = useTranslation();
  return <button>{t("button.submit")}</button>;
}

// 4. For formatting:
import { formatCurrency, formatDate } from "@/lib/i18n/formatters";
export function PriceDisplay({ amount, date }) {
  return <span>{formatCurrency(amount)} em {formatDate(date)}</span>;
}
```

#### 1.4 Locale Resolution Flow

**Server-side (layout, API routes):**
```
Request → getLocale() → reads Cloudflare context / defaults to "pt-BR" → returns locale
       → t(key) → looks up in catalog[locale][key] → returns string
```

**Client-side (components):**
```
Layout (server) renders → injects locale into LocaleProvider context
       → Client component → useTranslation() → reads context → t(key) → looks up
```

## Complexity Tracking

No violations of the Constitution. This feature is a straightforward, incremental addition with no architectural deviations.

| Aspect | Status | Notes |
|--------|--------|-------|
| No new npm/pip dependencies | ✅ PASS | Homegrown approach preferred; no `next-intl` or similar |
| Cloudflare Workers compatibility | ✅ PASS | No Node-only APIs; context and React features work on Edge |
| Type safety | ✅ PASS | TypeScript generics enforce catalog structure and key validation |
| Unit test pattern | ✅ PASS | Uses existing `node:test` + `.test.mjs` pattern |
