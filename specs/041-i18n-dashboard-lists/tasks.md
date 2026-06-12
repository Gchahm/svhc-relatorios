# Tasks: Localize the dashboard list pages to pt-BR

**Feature**: 041-i18n-dashboard-lists
**Spec**: [spec.md](./spec.md) · **Plan**: [plan.md](./plan.md) · **Contract**: [contracts/catalog-keys.md](./contracts/catalog-keys.md)

Tests requested by spec (FR-008/FR-010): the catalog-completeness `node:test` suite is extended.
No other test framework is configured (constitution III), so verification is the completeness
test + lint + format + build + manual UI.

## Phase 1: Setup

- [X] T001 Confirm the i18n foundation is present and read its public API in `src/lib/i18n/{index.ts,client.tsx,formatters.ts,catalog.ts}` (the `t`/`useTranslation`/`useLocale` APIs, the formatters' explicit-`locale` override, and the `getAlertTypeLabel` path) so all later tasks call them correctly.

## Phase 2: Foundational (blocks every page slice)

- [X] T002 Extend the catalog type + both locales in `src/lib/i18n/catalog.ts`: add the new sections/keys from `contracts/catalog-keys.md` (`filter`, `status`, `severity`, `alert_status`, `match`, `count` (`_one`/`_other`), `summary`, `meta`, `notice`, `action`, and the extensions to `table`/`form`/`page`) to `CatalogShape` and to BOTH `pt-BR` (canonical) and `en` (mirror). Keep alphabetical/section grouping consistent with the existing file.
- [X] T003 [P] Add the catalog-backed plural helper `plural(t, base, n)` in a client-safe module `src/lib/i18n/plural.ts` (pure, no server import): returns `t(\`${base}_one\`)` when `n === 1` else `t(\`${base}_other\`)`. Export the `base` keys' type.
- [X] T004 De-risk client formatter usage: verify a client component can import `formatCurrency`/`formatDate`/`formatPercent`/`formatNumber` from `@/lib/i18n/formatters` and call them with an explicit `locale` without dragging server-only code into the client bundle. If `pnpm build` (T028) later fails on server-only code, add a client-safe re-export module (e.g. re-export the formatters from `client.tsx` or a new `formatters.client.ts`) and point the list pages at it. (If a date-time format is needed for scrape-runs, extend `formatters.ts` with a shared `formatDateTime` rather than a per-file helper.)
- [X] T005 Extend the completeness test `src/lib/i18n/catalog.test.mjs`: add a test asserting every list-page required key from the contract resolves to a non-empty string in BOTH locales (mirror the existing I18N-002 `requiredKeys` test), and keep the structural-parity/no-empty/subset tests green.

**Checkpoint**: `node --test src/lib/i18n/catalog.test.mjs` passes with the new keys present.

---

## Phase 3: User Story 1 — list pages render entirely in pt-BR (P1)

**Goal**: Every chrome string in the listed clients + page titles + filter components resolves from the catalog; no raw snake_case alert type; status/severity/resolved badges localized; data verbatim.

**Independent test**: Visit each `/dashboard/*` list page; chrome is pt-BR, data verbatim.

- [X] T006 [P] [US1] Localize `src/components/filters/SortableHeader.tsx` (any aria-label / sort-direction affordance text) and `src/components/filters/CategoryTree.tsx` (chrome labels) via `useTranslation()`/`useLocale()`. Verify label props passed by callers (e.g. EntriesClient) are catalog-sourced.
- [X] T007 [US1] Localize `src/app/dashboard/entries/EntriesClient.tsx`: filter group labels (Period/Search/Document type/Attachment status), placeholders ("Select period"→`form.select_period`, "Search description..."→`form.search_placeholder`, "All"→`form.all`), `matchStatusOptions` labels (`match.*`), column-header `label=` props + the short "Doc/Amt/Vnd/Dt" headers, the summary badges (Revenue/Expenses/Net → `summary.*`), the docs/amount/vendor/date/errors summary nouns (`match.*`), the count ("N entries" → `plural`), the `Error:` prefix, row titles, and the in-file deep-link notice text (`notice.*`). Pass `useLocale()` to the shared formatters; DELETE the local `formatCurrency`/`formatDate`.
- [X] T008 [US1] Localize `src/app/dashboard/alerts/alerts.tsx`: `SeverityBadge` → `severity.*`, `StatusBadge` → `alert_status.*`, and the `KEY_LABELS` metadata map → `meta.*`. Because this module is server-importable AND used by client list rows, make the badge components read the locale safely (convert to client components with `useLocale()`/`useTranslation()`, or accept a resolved label) without breaking the detail page that imports `evidenceFields`; DELETE the local `formatCurrency`. (Keep `affectedEntryIds`/`entryHref`/`referencedDocumentId`/`evidenceFields` behavior identical.)
- [X] T009 [US1] Localize `src/app/dashboard/alerts/AlertsClient.tsx`: replace `alertTypeLabel()` from `@/lib/alerts` with the catalog `alert.types.*` path (client `useTranslation()`), with a humanized fallback (never raw snake_case) for unknown types; localize severity/period/type/status filter labels + options (`filter.*`, `severity.*`, `alert_status.*`), column headers (`table.*`), the count ("N alerts" → `plural`) and the active-count badges ("N critical/warning/info" → number + `severity.*`), the empty state ("No alerts found." → `form.no_alerts`), the `EntryLinks` "Open"/"Entry N"/"N entries" text, the row title, and the `Error:` prefix.
- [X] T010 [P] [US1] Localize `src/app/dashboard/documents/StatusBadge.tsx` → `status.*` (over/within/under/unknown) via `useLocale()`/`useTranslation()` (make it a client component if needed; it's also used by the detail page — keep it self-contained).
- [X] T011 [US1] Localize `src/app/dashboard/documents/DocumentsClient.tsx`: title suffix decision ("(Notas Fiscais)" kept as domain term), Type/Search filter labels + placeholders ("All types"→`form.all_types`, "NF number or issuer…"→`form.search_doc_placeholder`, "Search (number / issuer)"→`form.search_number_issuer`), column headers (`table.number/issuer/type/total/sum_entries/links/status`), the count ("N documents" → `plural`), empty state ("No documents found." → `form.no_documents`), row title, and `Error:` prefix. Pass `useLocale()` to the shared `formatCurrency`; DELETE the local helper.
- [X] T012 [P] [US1] Localize `src/app/dashboard/reports/ReportsClient.tsx`: title ("Prestações de Contas" kept/normalized), the "N períodos" count (`plural`/`count.periods`), "Loading..."→`form.loading`, column headers (Período/Receitas/Despesas/Saldo Mês/Saldo Acumulado → `table.*`), `Error:` prefix; pass `useLocale()` to shared `formatCurrency`; DELETE the local helper.
- [X] T013 [P] [US1] Localize `src/app/dashboard/fines/FinesClient.tsx`: title (Multas), filter labels (Period/Block/Reason → `filter.*`) + "All", block option label ("Bloco {v}" — keep "Bloco" via `filter.block`/a `count`-free label), the count ("N fine(s)" string-concat → `plural`/`count.fines`), Total badge, column headers (Period/Date/Unit/Reason/Amount → `table.*`), `Error:` prefix; pass `useLocale()` to shared `formatCurrency`/`formatDate`; DELETE the local helpers.
- [X] T014 [P] [US1] Localize `src/app/dashboard/comparison/ComparisonClient.tsx`: all chrome (period selectors, Receita/Despesa labels, column headers, diff labels, count, empty/loading/error), DELETE the local `formatCurrency`, use shared formatters with `useLocale()`.
- [X] T015 [P] [US1] Localize `src/app/dashboard/summary/SummaryClient.tsx`: Revenue/Expenses/Net summary, column headers, count, totals, loading/empty/error; DELETE the local `formatCurrency`; shared formatters + `useLocale()`.
- [X] T016 [P] [US1] Localize `src/app/dashboard/scrape-runs/ScrapeRunsClient.tsx`: title, column headers, status text, count ("N runs" → `plural`), loading/empty/error; replace the local `formatDateTime` with a shared formatter (extend `formatters.ts` if needed — T004) + `useLocale()`.
- [X] T017 [P] [US1] Localize `src/app/dashboard/units/UnitsClient.tsx`: title, filters, column headers, count ("N units" → `plural`), totals, loading/empty/error; DELETE the local `formatCurrency`; shared formatter + `useLocale()`.
- [X] T018 [P] [US1] Localize `src/app/dashboard/vendors/VendorsClient.tsx`: title, filters, column headers, count ("N vendors" → `plural`), Total, the share `formatPercent`, loading/empty/error; DELETE the local `formatCurrency`/`formatPercent`; shared formatters + `useLocale()`.
- [X] T019 [P] [US1] Localize `src/app/dashboard/document-analyses/page.tsx` (and its client if any) chrome.
- [X] T020 [P] [US1] Localize the page titles/descriptions in each `page.tsx` (server component) via `t()`: `entries`, `alerts`, `documents`, `reports`, `fines`, `comparison`, `summary`, `scrape-runs`, `units`, `vendors`, `document-analyses` — `page.*_title` / `page.*_description`.

**Checkpoint**: every list page renders pt-BR chrome; alert types localized; status/severity/resolved badges localized.

---

## Phase 4: User Story 2 — counts & formatting (P2)

**Goal**: counts pluralize correctly (0/1/many) and money/date/percent use Brazilian format via the shared formatters.

**Independent test**: filter a list to 1 row vs many; confirm singular/plural and Brazilian number/date formatting.

- [X] T021 [US2] Audit every count summary touched in Phase 3 to confirm it uses `plural(t, "count.<noun>", n)` (no English-suffix concatenation remains; the fines `fine${n!==1?"s":""}` and any `entries`/`alerts`/`documents` literal are gone). Confirm the 0/1/many boundaries read correctly in pt-BR.
- [X] T022 [US2] Audit every money/date/percent render touched in Phase 3 to confirm it calls the shared `formatCurrency`/`formatDate`/`formatPercent`/`formatNumber` with `useLocale()`; grep-confirm no `toLocaleString(...)` / private formatter remains in the listed files (SC-002).

---

## Phase 5: User Story 3 — behavior unchanged (P2)

**Goal**: filtering, sorting, deep links, virtualization, dialogs work exactly as before.

**Independent test**: exercise sort/filter/period-select and an alert→entry deep link before/after.

- [X] T023 [US3] Verify EntriesClient deep-link still resolves, scrolls, highlights, and auto-opens the analysis dialog; the filter-recovery path and URL param stripping are unchanged (only strings changed).
- [X] T024 [US3] Verify sort toggles (SortableHeader), MultiSelect/Select filters, and virtualized scrolling behave identically across all touched pages (string-only changes; no logic/keys/values altered).
- [X] T025 [US3] Verify the `alerts.tsx` badge refactor (if converted to client components) did not break the alert detail page's server-side import of `evidenceFields`/`SeverityBadge`/`StatusBadge`.

---

## Phase 6: Polish & Cross-Cutting

- [X] T026 Run `pnpm lint` and fix any issues in touched files.
- [X] T027 Run `pnpm exec prettier --write` on touched files, then `--check` to confirm format (constitution III: 4-space tabs, 120 width, double quotes, ES5 trailing commas).
- [X] T028 Run `pnpm build` (OpenNext/Next) to confirm the client/server import split holds (no server-only code in client bundles); apply the T004 client-safe re-export fallback if needed.
- [X] T029 Run `node --test src/lib/i18n/catalog.test.mjs` (and `pnpm test`) — completeness + parity green.
- [X] T030 Run the SC-002 grep gates from `quickstart.md`; confirm no private formatter / removed English literal remains in the listed files.
- [X] T031 Manual UI verification (`ui-login` skill) across all pages per `quickstart.md`; record the results for the PR body.

## Dependencies

- Phase 2 (T002–T005) blocks all of Phase 3+.
- T002 (catalog) blocks every localization task (they reference the keys).
- T004 (formatter de-risk) blocks the formatter swaps in T007/T011–T018 and is confirmed by T028.
- T003 (plural) blocks the count tasks in T007/T009/T011–T018 and the T021 audit.
- Phase 3 tasks marked [P] touch independent files and can run in parallel after Phase 2.
  T007/T009 (entries/alerts clients) depend on T006 (filters) and T008/T010 (badge modules) respectively.
- Phases 4–6 are audits/gates after Phase 3.

## Parallel execution example

After Phase 2 completes, the per-page slices that touch disjoint files can proceed together:
T010, T012, T013, T014, T015, T016, T017, T018, T019, T020 are all `[P]`. T006 should land before
T007; T008+T010 before the clients that consume those badges.

## Implementation strategy

MVP = Phase 2 + Phase 3 (US1) for the three pages named in the issue's acceptance scenarios
(entries, alerts, documents) — that already delivers the visible outcome. Then fan out the
remaining pages, then run the US2/US3 audits and the Phase 6 gates.
