# Data Model: Preserve Raw Portal Values on Mirror Rows

## Modified entity: `entries` (mirror table — scraper-owned)

Two new **nullable** columns. All existing columns unchanged.

| Column            | Type            | Null? | Owner   | Meaning |
|-------------------|-----------------|-------|---------|---------|
| `raw_amount`      | TEXT            | YES   | scraper | Verbatim portal cell text for the amount, before any parsing (e.g. `"R$ 1.234,56"`). |
| `raw_description` | TEXT            | YES   | scraper | Verbatim portal cell text for the description, before whitespace normalization and fornecedor-prefix stripping. |

Drizzle (`src/db/fiscal.schema.ts`, in the `entries` table block):

```ts
rawAmount: text("raw_amount"),            // verbatim portal amount cell text (provenance, IMP-001)
rawDescription: text("raw_description"),  // verbatim portal description cell text (pre-normalization)
```

### Constraints / rules

- **Nullable**: existing rows (scraped before this feature) read back as `NULL`; re-scraping a period
  populates both (FR-007, FR-008).
- **Scraper-owned**: written ONLY by the scraper in `_scrape_periodo`'s entry-row build; the analysis
  pipeline never reads or writes them (mirror invariant, feature 026 / FR-003).
- **No index**: provenance columns are for point lookups by entry id / ad-hoc audit queries, not hot
  query paths — no index added (constitution V, simplicity).
- **No FK / uniqueness**: free text.

### Relationship to derived columns

- `raw_amount` ↔ `amount` (REAL): `amount` is `parse_brl(raw_amount)` when parseable. Round-trip
  invariant: for every stored row, `parse_brl(raw_amount) == amount` (SC-003). A row whose
  `raw_amount` does not parse is **not stored** (row-skip policy) — so no stored row has an
  unparseable `raw_amount`.
- `raw_description` ↔ `description` (TEXT): `description` is
  `_strip_fornecedor_prefix(_normalize_whitespace(raw_description))`. They are equal when the raw text
  needed no normalization and had no fornecedor prefix.

## Parser contract: `parse_brl`

```
parse_brl(text: str) -> float | None
```

- Returns the parsed value for a well-formed BRL string (`"R$ 1.234,56"` → `1234.56`).
- Returns `None` when: input is empty/whitespace-only, contains no parseable number, or the parse
  yields `NaN` / `±inf` (rejected via `math.isfinite`). Never raises for malformed input.

## Failure-handling state (no new persisted entity)

Row-level parse skips are **not** a new table/column. They are recorded as **non-fatal run notes**
merged into the existing `scrape_runs.errors` text (the IMP-002 channel), e.g.:

```
Parse skipped 1 entry row(s) in 2026-01: amount cell "R$ --,--" (desc "TAXA ...")
```

The run's `status` stays `success` if no fatal error occurred (FR-006).
