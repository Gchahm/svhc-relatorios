# Implementation Plan: Localize the dashboard list pages to pt-BR

**Branch**: `041-i18n-dashboard-lists` | **Date**: 2026-06-12 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/041-i18n-dashboard-lists/spec.md`

## Summary

Route every user-facing chrome string in the dashboard list pages (entries, alerts, documents, reports, fines, comparison, summary, scrape-runs, units, vendors, document-analyses) and the shared filter components through the I18N-001 typed message catalog, render pt-BR by default, and replace each page's private `formatCurrency`/`formatDate`/`formatPercent`/`formatDateTime` helper with the shared locale-aware formatters (passing the active `useLocale()` locale). Alert type labels come from the localized `alert.types.*` path (never raw snake_case); reconciliation status (over/within/under/unknown) and severity badges are localized; count summaries pluralize via a small catalog-backed `_one`/`_other` mechanism. Data values from D1 render verbatim. No schema/data change; behavior preserved.

## Technical Context

**Language/Version**: TypeScript 5 / React 19 / Next.js 15 (App Router); Node 22 for the test runner
**Primary Dependencies**: Existing only — the I18N-001 catalog/formatters (`src/lib/i18n/*`), shadcn/ui, `@tanstack/react-virtual`, lucide-react. No new npm dependency.
**Storage**: N/A — presentation-layer change; reads no new data, writes nothing; no D1 schema/migration.
**Testing**: Node `node:test` (the catalog-completeness suite `src/lib/i18n/catalog.test.mjs`); `pnpm lint`; Prettier format check; manual UI verification against local prod-like D1.
**Target Platform**: Cloudflare Workers (OpenNext) — browser-rendered client components + server `page.tsx`.
**Project Type**: Web (Next.js single app).
**Performance Goals**: No regression — virtualized lists and filters behave identically; translation is a synchronous in-memory dictionary lookup.
**Constraints**: Client components must not import the server-only `@/lib/i18n` barrel or call `getLocale()`; they use `@/lib/i18n/client` + explicit-locale formatters. `en` must stay a structural subset/parity of pt-BR (completeness test). Mirror-data values are never translated.
**Scale/Scope**: 13 list clients + their `page.tsx` titles + 2 shared filter components + catalog extension + completeness-test extension. ~2,900 lines surveyed; the change is string-extraction + formatter swaps, mechanical and localized per file.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- **I. Type Safety & Schema Discipline**: PASS — `DeepCatalogKey` is type-checked, so every `t("…")` call is compile-validated. No `any`. No schema/Drizzle change (presentation only).
- **II. Cloudflare-Native Architecture**: PASS — no DB access added; no new bindings. Client/server import split honored (no server-only code in client bundle).
- **III. Quality Gates Before Commit**: PASS — `pnpm lint` + Prettier are run before commit; the existing `node:test` catalog suite is extended and must pass; manual UI verification is part of the PR phase.
- **IV. Security & Auth by Default**: PASS — no route/auth change; pages remain auth-gated as before.
- **V. Simplicity & Incremental Delivery**: PASS — reuses the shipped catalog/formatters; the plural helper is a ~5-line pure function with no dependency. Each page is an independent slice.

No violations → Complexity Tracking not required.

## Project Structure

### Documentation (this feature)

```text
specs/041-i18n-dashboard-lists/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   └── catalog-keys.md
├── checklists/
│   └── requirements.md
└── tasks.md            # speckit tasks output
```

### Source Code (repository root)

```text
src/
├── lib/i18n/
│   ├── catalog.ts            # EXTEND: add list-page sections (table headers, filters, badges,
│   │                         #   status, severity, counts, page titles/descriptions, per-page labels)
│   │                         #   in BOTH pt-BR and en + extend CatalogShape type
│   ├── catalog.test.mjs      # EXTEND: assert the new required keys resolve non-empty in both locales
│   ├── client.tsx            # (maybe) add a client-safe formatter re-export / plural helper if needed
│   └── plural.ts             # NEW (small): catalog-backed plural(t, base, n) helper (or colocated)
├── components/filters/
│   ├── SortableHeader.tsx    # localize any aria-label / sort affordance text
│   └── CategoryTree.tsx      # localize chrome labels
└── app/dashboard/
    ├── entries/{EntriesClient.tsx,page.tsx}
    ├── alerts/{AlertsClient.tsx,alerts.tsx,page.tsx}
    ├── documents/{DocumentsClient.tsx,StatusBadge.tsx,page.tsx}
    ├── reports/{ReportsClient.tsx,page.tsx}
    ├── fines/{FinesClient.tsx,page.tsx}
    ├── comparison/{ComparisonClient.tsx,page.tsx}
    ├── summary/{SummaryClient.tsx,page.tsx}
    ├── scrape-runs/{ScrapeRunsClient.tsx,page.tsx}
    ├── units/{UnitsClient.tsx,page.tsx}
    ├── vendors/{VendorsClient.tsx,page.tsx}
    └── document-analyses/page.tsx
```

**Structure Decision**: Single Next.js app. The change is confined to `src/lib/i18n/*` (catalog + helper + test) and the in-scope dashboard clients / page titles / filter components. No new top-level directories.

## Phase 0: Outline & Research

Complete — see [research.md](./research.md). All clarifications resolved (R1–R8). Key risk: client-safe formatter import (R6), de-risked by passing explicit locale + a verified build, with a client-safe re-export fallback.

## Phase 1: Design & Contracts

- [data-model.md](./data-model.md) — catalog sections/keys (the "entities" here are message-catalog sections), the plural helper contract, and the formatter call convention.
- [contracts/catalog-keys.md](./contracts/catalog-keys.md) — the exhaustive list of new catalog keys each page consumes (the contract the completeness test enforces).
- [quickstart.md](./quickstart.md) — how to verify locally.

## Re-evaluation (post-design)

Constitution Check still PASSES after design: no new dependency, no schema change, type-checked keys, client/server split preserved. Proceed to `speckit tasks`.
