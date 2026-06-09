# Data Model: Merge Document Analyses into the Entries page

No database schema changes. This feature is read-only over existing D1 tables. The model below describes the **view-model** shapes the merged client composes from two existing endpoints.

## Persisted entities (existing, read-only)

- **entries** — ledger lines: `id`, `date`, `description`, `amount`, `movementType` (C/D), `reportId`, `subcategoryId`, `vendorId`, `unitId`.
- **accountability_reports** — `id`, `period` (`YYYY-MM`). An entry's period = its report's period (via `entries.reportId`).
- **documents** — `id`, `entryId` (→ entries), file/page references.
- **document_analyses** — per-entry roll-up: `id`, `documentId`, `analyzedAt`, `documentType`, `extractedAmount`, `amountMatch`, `extractedCnpj`, `issuerName`, `vendorMatch`, `extractedDate`, `dateMatch`, `documentNumber`, `serviceDescription`, `error`.
- **document_analysis_records**, page images (R2) — consumed only by the detail dialog via its existing per-analysis routes; unchanged.

## View-model shapes (client)

### `Entry` (existing, unchanged)

`id, date, description, amount, movementType, sourceUrl, period, category, subcategory, vendor, unitCode` — from `GET /api/entries?period=P`.

### `DocAnalysisRow` (existing shape; now also exported from `EntriesClient.tsx`)

Returned by `GET /api/document-analyses[?period=P]`, one object per analysis:

```
id, documentId, analyzedAt, documentType,
extractedAmount, amountMatch, extractedCnpj, issuerName, vendorMatch,
extractedDate, dateMatch, documentNumber, serviceDescription, error,
entryId, entryDate, entryDescription, entryAmount, entryMovementType,
vendorName, subcategoryName, categoryName
```

The detail dialog consumes this object directly and self-fetches records/pages by `id`. **Shape is unchanged** — only the optional `period` filter is added to the route.

### Derived: `analysisByEntry: Map<string, DocAnalysisRow>`

Built in `EntriesClient` after both fetches resolve:
- Key: `entryId` (string).
- Value: the **latest** analysis for that entry (endpoint orders `analyzedAt DESC`; first occurrence per `entryId` wins).
- Entries absent from the map have no analysed document → neutral/empty document state.

### Derived: per-entry `MatchStatus`

For an entry present in the map:
- `amountMatch`, `vendorMatch`, `dateMatch`: `true | false | null` (null = unknown/not applicable → em-dash, **not** a mismatch).
- `hasError`: `!!error`.
- `hasMismatch`: any of the three === `false`.
- `allMatch`: none === `false` and `!hasError`.

Used by the inline badges, the document-type/match-status filters, and the period summary.

### Derived: period document-health `summary`

Over the period-scoped analyses currently loaded: `total`, `errors`, `amountBad`, `vendorBad`, `dateBad` (mirrors the standalone page's summary memo, scoped to the period).

## Relationships & rules

- **entry 1—0..1 (rolled-up) analysis** on the merged row: an entry maps to at most one displayed analysis status (latest); multiple page-records/siblings are handled inside the detail dialog as today.
- **Period scoping**: both endpoints are filtered to the selected period; the analysis map only contains the period's analyses, so the join can never attach an out-of-period analysis.
- **Filters compose with AND**: document-type and match-status filters AND with the existing category and search filters; all reset on period change.
