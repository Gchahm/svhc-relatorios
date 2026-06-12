# Feature Specification: Localize the dashboard list pages to pt-BR

**Feature Branch**: `041-i18n-dashboard-lists`  
**Created**: 2026-06-12  
**Status**: Draft  
**Input**: User description: "Localize all dashboard list pages to pt-BR via the I18N-001 catalog and I18N-002 glossary: table headers, filters, badges, empty states, plurals; replace local format helpers with the shared formatters"

## Context

The condominium fiscal-audit dashboard has a set of list/working pages (entries, alerts, documents, reports, fines, comparison, summary, scrape-runs, units, vendors, document-analyses) that today render a mix of hardcoded English and ad-hoc Portuguese text: table headers, filter placeholders, status/severity badges, empty states, count summaries, sort labels, and loading states. Each page also carries its own copy of `formatCurrency` / `formatDate` / `formatPercent` / `formatDateTime` helpers.

Features I18N-001 (#64) and I18N-002 (#65) already shipped: a typed message catalog (`src/lib/i18n/catalog.ts`) with pt-BR as the canonical/default locale, server (`t`) and client (`useTranslation`) lookup APIs, locale-aware shared formatters, a `getAlertTypeLabel()` path, and a catalog-completeness test. The auth pages and dashboard shell are already localized. This feature finishes the job for the list pages.

## Clarifications

### Session 2026-06-12

(Unattended `full` run — decisions made by the implementer per best practice and recorded here instead of asking.)

- Q: What concrete shape does the catalog-backed plural mechanism take (A3)? → A: A `count` catalog section holding `<noun>_one` / `<noun>_other` keys (e.g. `count.entries_one` = "lançamento", `count.entries_other` = "lançamentos") plus a tiny client helper `plural(t, base, n)` that selects `_one` when `n === 1` else `_other` and the caller prepends the formatted number. No ICU dependency.
- Q: Should the `en` locale receive every new list-page key, or only sections it already mirrors (A1)? → A: Every new key is added to BOTH `pt-BR` and `en` (full structural parity), so the existing completeness test's subset/parity/no-empty assertions all hold without weakening them.
- Q: How do client components obtain the locale for the shared formatters (A2)? → A: Via the existing `useLocale()` hook from `@/lib/i18n/client`, passed as the explicit `locale` argument to each `formatCurrency`/`formatDate`/`formatPercent`/`formatNumber` call (the formatters already accept a `locale?` override; their default `getLocale()` is server-only and must not run in a client bundle).

## User Scenarios & Testing *(mandatory)*

### User Story 1 - List pages render entirely in pt-BR (Priority: P1)

A condominium board member opens any dashboard list page (e.g. Lançamentos, Alertas, Documentos). Every piece of UI chrome — page title and description, table column headers, filter labels and placeholders, sort affordances, status and severity badges, empty/loading/error states, and count summaries — reads in natural pt-BR. The data rows themselves (descriptions, vendor names, portal text scraped from brcondos) are shown verbatim, untranslated, because they are mirror data.

**Why this priority**: This is the entire point of the feature and the user-visible outcome. A board member who does not read English must be able to work the audit surfaces.

**Independent Test**: Log into the running app, visit each `/dashboard/*` list page against the local prod-like D1 data, and confirm no English chrome remains while data values stay verbatim.

**Acceptance Scenarios**:

1. **Given** the default locale (pt-BR), **When** a user opens `/dashboard/entries`, **Then** the page title, column headers (Período/Data/Valor/Fornecedor/Descrição/Documento), filter placeholders ("Selecione um período", "Pesquisar por descrição..."), and the revenue/expense/net summary read in pt-BR, while each entry's `description` and vendor name render exactly as stored.
2. **Given** the Alertas page, **When** alerts of various types are listed, **Then** each alert's type renders as a localized label (never a raw `snake_case` string), its severity renders as a localized badge, and resolved/unresolved state reads in pt-BR.
3. **Given** the Documentos page, **When** documents with different reconciliation states are listed, **Then** the over/within/under/unknown status badge text reads in pt-BR.
4. **Given** any list page with no matching rows, **When** the filtered result set is empty, **Then** an empty-state message reads in pt-BR.

---

### User Story 2 - Counts and totals pluralize and format correctly (Priority: P2)

When a list page shows a count ("N lançamentos", "N alertas") or a money/percent/date value, the count pluralizes correctly in pt-BR and the value uses Brazilian formatting (R$ 1.234,56; 12/06/2026; 75,0%).

**Why this priority**: Incorrect plurals or en-US number/date formatting reads as broken/foreign even when the words are translated; it undermines the localization.

**Independent Test**: Filter a list to exactly 1 row and to many rows and confirm the count noun is singular vs plural; confirm currency/date/percent render in Brazilian format.

**Acceptance Scenarios**:

1. **Given** a list filtered to exactly 1 row, **When** the count summary renders, **Then** it uses the singular form (e.g. "1 lançamento").
2. **Given** a list with 2+ rows, **When** the count summary renders, **Then** it uses the plural form (e.g. "12 lançamentos").
3. **Given** any monetary cell, **When** it renders, **Then** it shows as `R$ 1.234,56` (pt-BR currency), produced by the shared formatter rather than a per-file helper.

---

### User Story 3 - Behavior is unchanged (Priority: P2)

All existing interactions — filtering, sorting, deep links into entries, virtualized scrolling, dialogs opening — continue to work exactly as before after the strings are routed through the catalog and the local format helpers are removed.

**Why this priority**: Localization must be behavior-preserving; a regression in sort/filter/deep-link would be worse than untranslated text.

**Independent Test**: Exercise sort toggles, filters, period selection, and an alert→entry deep link before and after; behavior is identical.

**Acceptance Scenarios**:

1. **Given** a sortable column, **When** the user clicks the header, **Then** the sort toggles and the (now-localized) sort affordance reflects direction exactly as before.
2. **Given** an alert with affected entries, **When** the user clicks a deep link, **Then** it navigates and highlights the entry exactly as before.

### Edge Cases

- A new catalog key is referenced but missing from a locale: the lookup falls back to pt-BR and logs a warning; the completeness test catches missing keys at build/test time.
- A data value happens to be English (e.g. a vendor name) — it is NOT translated; only UI chrome is.
- An alert `type` value not present in the catalog's `alert.types` map: it must still render a human-readable label, never raw `snake_case` (handled by the existing `getAlertTypeLabel` path / its fallback).
- A count of zero rows: the empty-state message shows rather than a "0 items" summary, matching prior behavior where applicable.
- A locale other than pt-BR (the catalog also carries `en`): chrome must resolve from that locale where present and fall back to pt-BR otherwise; the default remains pt-BR.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: Every user-facing chrome string in the listed clients and the shared filter components MUST resolve from the I18N-001 message catalog — column headers, filter labels/placeholders, badge texts (severity; reconciliation status over/within/under/unknown; resolved/unresolved), empty states, loading states, error states, button labels, aria-labels, sort labels, and count/summary strings.
- **FR-002**: Each affected page's `page.tsx` title/description MUST resolve from the catalog (server-side `t`), consistent with how I18N-002 localized other page titles.
- **FR-003**: The per-file `formatCurrency` / `formatDate` / `formatPercent` / `formatDateTime` / `formatNumber` helpers MUST be removed and replaced with the shared locale-aware formatters from I18N-001 (`src/lib/i18n/formatters.ts`). No list page may keep a private money/date/percent formatter.
- **FR-004**: Alert type labels MUST come from the localized alert-type path (the `getAlertTypeLabel` / `alert.types.*` catalog established in feature 038 and localized in I18N-001). No surface may render a raw `snake_case` alert type, in any locale.
- **FR-005**: Pluralized strings (e.g. entry/alert counts) MUST pluralize correctly in pt-BR via a catalog-backed mechanism, not by string concatenation of an English suffix.
- **FR-006**: Data values originating from D1 (entry descriptions, vendor names, scraped portal text, document numbers, CNPJs) MUST render verbatim and MUST NOT be translated — they are mirror data.
- **FR-007**: Filtering, sorting, deep links (alert→entry), period selection, dialog opening, and virtualized scrolling MUST behave exactly as before the change.
- **FR-008**: All new catalog keys MUST be present in the canonical pt-BR locale and, mirrored into the `en` locale, so the completeness test's pt-BR-superset and structural-parity assertions pass. The completeness test MUST cover the newly added keys.
- **FR-009**: An automated check (grep over the edited files for the removed English literals / local helper definitions) MUST come up empty, confirming no hardcoded chrome string or private formatter remains in the listed files.
- **FR-010**: `pnpm lint`, `pnpm format` (check), and the existing `node:test` suites MUST pass.

### Key Entities *(include if feature involves data)*

- **Message catalog**: The typed nested dictionary in `src/lib/i18n/catalog.ts`, keyed by locale (`pt-BR` canonical, `en` fallback). This feature extends it with the list-page sections (table headers, filters, badges, status, counts, page titles/descriptions, per-page domain labels).
- **Shared formatters**: The locale-aware `formatCurrency`/`formatDate`/`formatPercent`/`formatNumber`/`formatDuration` in `src/lib/i18n/formatters.ts`. They accept an explicit `locale` override so client components can pass the active locale.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Every `/dashboard/*` list page shows pt-BR UI chrome by default; a reviewer scanning each page finds no English chrome string.
- **SC-002**: A `grep` for the removed English literals and the local `function formatCurrency`/`formatDate`/`formatPercent`/`formatDateTime` definitions over the listed files returns no matches.
- **SC-003**: No surface renders a raw `snake_case` alert type; every alert row shows a human-readable localized label.
- **SC-004**: Count summaries pluralize correctly for the boundary cases of 0, 1, and many rows in pt-BR.
- **SC-005**: Filtering, sorting, deep links, and virtualized scrolling produce identical behavior before and after the change (verified manually against local prod-like data).
- **SC-006**: `pnpm lint`, Prettier format check, and the `node:test` catalog-completeness suite all pass.

## Assumptions

- **A1 (catalog is canonical-pt-BR + mirrored-en)**: pt-BR is the canonical, complete locale; `en` mirrors the full structure. New list-page keys are added to BOTH locales to keep them parallel (the completeness test requires `en` to be a subset of pt-BR and asserts structural parity / no empty strings).
- **A2 (client components pass an explicit locale to formatters)**: `formatters.ts` derives the locale from the server-only `getLocale()` when no override is given. The list pages are client components, so they will pass the active locale (from the `useLocale()` client hook) explicitly to each formatter call. This preserves the "shared formatter" requirement without dragging server-only code into the client bundle.
- **A3 (plural mechanism)**: I18N-001 ships no ICU/plural engine. We will add a tiny catalog-backed pluralization for the few count nouns used (singular vs plural key, selected by count), rather than an English-suffix concatenation. The pt-BR plural rule used is "n === 1 → singular, else plural", which is correct for the count nouns on these pages.
- **A4 (already-Portuguese strings still get routed through the catalog)**: Some pages already contain hand-written Portuguese (reports, comparison, scrape-runs, fines). To centralize the glossary and satisfy "no hardcoded chrome string remains," those literals are also moved into the catalog (their pt-BR value preserved/normalized to the glossary).
- **A5 (data is never translated)**: Entry descriptions, vendor names, document numbers, CNPJs, and any scraped portal text render verbatim (mirror-data invariant). Only static UI chrome is localized.
- **A6 (no schema/data change)**: This is a presentation-layer change. No D1 schema, migration, or data write is involved; API routes are unchanged.
- **A7 (scope = the files named in issue #66)**: The clients, their `page.tsx` titles, and the shared filter components under `src/components/filters/`. Detail pages, dialogs, and notices are out of scope (issue #67 / I18N-004). The `AttachmentAnalysisDetailDialog` and similar are left to that follow-up; this feature touches the list surfaces only.

## Dependencies

- Depends on #64 (I18N-001 foundation — catalog, lookup APIs, formatters) — merged.
- Glossary from #65 (I18N-002) — merged.
