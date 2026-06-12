# Data Model: Localize the dashboard list pages to pt-BR

This feature has no persisted-data model (no D1 schema). The "entities" are message-catalog
sections and two small helpers. All values are static UI strings.

## Catalog sections (extend `CatalogShape` + both locale objects)

The existing sections (`nav`, `app`, `access`, `button`, `page`, `dialog`, `table`, `form`,
`badge`, `alert`, `error`, `common`, `auth`, `formatting`) are kept. We ADD/EXTEND:

### `table` (extend)
Existing: period, date, amount, vendor, description, attachment, actions, status, type.
Add the column headers used by the list pages: `category`, `subcategory`, `unit`, `doc`,
`title`, `severity`, `entries`, `number`, `issuer`, `total`, `sum_entries`, `links`,
`revenue`, `expenses`, `month_balance`, `accumulated_balance`, `reason`, `block`, `share`,
`run`, `executed_at`, `periods_scraped`, `attachments`, `errors`, `name`.
(Short header abbreviations like "Amt"/"Vnd"/"Dt" get keys `amt`/`vnd`/`dt`.)

### `form` (extend)
Existing: search_placeholder, select_period, select_placeholder, no_results, loading.
Add: `all` ("Todos"), `all_types` ("Todos os tipos"), `search_doc_placeholder`
("Número da NF ou emitente…"), `search_number_issuer` ("Buscar (número / emitente)").

### `filter` (NEW)
Sidebar/filter group labels: `period`, `search`, `document_type`, `attachment_status`,
`severity`, `type`, `status`, `block`, `reason`, `category`, `subcategory`.

### `status` (NEW) — document reconciliation
`over`, `within`, `under`, `unknown` (localized badge text for `DocumentStatus`).

### `severity` (NEW) — alert severity
`critical`, `warning`, `info` (localized badge + filter-option labels).

### `alert_status` (NEW) — alert resolved state
`active`, `resolved`.

### `match` (NEW) — attachment match-status filter + per-row summary nouns
`all_match`, `has_mismatch`, `has_error`, `amount`, `vendor`, `date`, `errors`, `docs`.

### `count` (NEW) — pluralized nouns (`_one` / `_other`)
`entries_one`/`entries_other`, `alerts_one`/`alerts_other`, `documents_one`/`documents_other`,
`fines_one`/`fines_other`, `periods_one`/`periods_other`, `units_one`/`units_other`,
`vendors_one`/`vendors_other`, `runs_one`/`runs_other`.
(Also severity-count nouns reuse `severity.*` + a number; alert summary "N critical" uses
`severity.critical` lowercase form — see contract.)

### `page` (extend)
Add `_title`/`_description` for the pages not yet present: reports, fines, comparison,
summary, scrape_runs (runs), units, vendors, document_analyses.

### `alert.types` (already exists, feature 038/I18N-001)
Used as-is via `getAlertTypeLabel` (server) / `t("alert.types.<type>")` (client). A fallback
humanizer (replace `_`→space, never raw snake_case) covers any type absent from the map.

### `summary` / per-page labels (NEW small section as needed)
e.g. `entries.revenue` / `entries.expenses` / `entries.net` summary prefixes, the metadata
`KEY_LABELS` map in `alerts.tsx` (Document total, Sum of entries, …). These move into a
catalog section (e.g. `meta.*`) so the alert detail/evidence labels are localized too where
they live in a listed file.

> NOTE: The exhaustive, file-by-file key list is the contract in `contracts/catalog-keys.md`.
> Both `pt-BR` and `en` receive every added key (A1 / completeness test).

## Helper: `plural(t, base, n)` — catalog-backed pluralization

- **Location**: a small client-safe module (e.g. `src/lib/i18n/plural.ts`) or colocated in
  `client.tsx`. Pure, no dependency.
- **Signature**: `plural(t: (k: DeepCatalogKey) => string, base: "count.entries" | …, n: number): string`
  → returns `t(\`${base}_one\`)` when `n === 1`, else `t(\`${base}_other\`)`.
- **Usage**: `${n} ${plural(t, "count.entries", n)}` → "1 lançamento" / "12 lançamentos".
- **Rule**: pt-BR `n === 1 → _one`, else `_other` (correct for these count nouns).

## Convention: shared formatters with explicit locale

- Client components: `const locale = useLocale();` then `formatCurrency(value, locale)`,
  `formatDate(iso, locale)`, `formatPercent(value, decimals, locale)`,
  `formatNumber(value, decimals, locale)`.
- Server `page.tsx`: `formatCurrency(value)` (default locale via `getLocale()`), or `t(...)`.
- Per-file `formatCurrency`/`formatDate`/`formatPercent`/`formatDateTime` definitions are deleted.
- `formatDateTime(ts)` (scrape-runs) → replaced by `formatDate` + a time portion via a shared
  formatter call (or `Intl.DateTimeFormat` is consolidated into `formatters.ts` if a date-time
  variant is needed — prefer extending the shared formatter over a per-file helper).

## State transitions

None — purely presentational.
