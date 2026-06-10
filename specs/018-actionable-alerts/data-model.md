# Data Model: Actionable Alerts

**No D1 schema change.** `alerts.metadata` (JSON text) already exists. This documents the
data shapes that flow through that column and across the API → UI seam.

## Entities (existing, read/written as-is)

### Alert (`alerts` table)
- `id` (text, deterministic UUID — `det_id("alert", period, type, discriminator)`)
- `type` (text) — alert kind discriminator (new values added; see below)
- `severity` (text) — `critical` | `warning` | `info`
- `title`, `description` (text, human-readable, pt-BR)
- `reference_period` (text, `YYYY-MM`)
- `metadata` (text, JSON) — **now surfaced to the UI**
- `resolved` (int), `resolved_at` (int|null), `notes` (text|null) — human triage state,
  independent of the loop's verdicts (FR-011)

### Entry (`entries` table) — read only
- `id` (text UUID) — the deep-link key (FR-015)

### AttachmentAnalysis (`attachment_analyses`) — read only by detection
- `attachment_id`, `amount_match` (0/1/null), `vendor_match`, `date_match`, `error`,
  `extracted_amount`, `issuer_name`, `extracted_date` — the persisted, reconciliation-aware
  match flags the detector reads (R2).

## New alert types (written by `check_attachment_mismatches`)

| `type`                         | severity | when                                   |
|--------------------------------|----------|----------------------------------------|
| `attachment_amount_mismatch`   | warning  | `attachment_analyses.amount_match = 0` |
| `attachment_vendor_mismatch`   | warning  | `vendor_match = 0`                     |
| `attachment_date_mismatch`     | warning  | `date_match = 0`                       |
| `attachment_page_error`        | info     | `error` is set                         |

`discriminator = attachment_id` (type already encodes kind) → id stable across re-runs (FR-003).

### Metadata shape for the new alerts

```json
{
  "attachment_id": "<uuid>",
  "entry_id": "<uuid|null>",
  "kind": "amount" | "vendor" | "date" | "page-error",
  "ledger_value": <number|string|null>,
  "extracted_value": <number|string|null>
}
```

- `amount`: `ledger_value` = entry amount, `extracted_value` = `extracted_amount`.
- `vendor`: `ledger_value` = ledger vendor name, `extracted_value` = `issuer_name`.
- `date`: `ledger_value` = period (`YYYY-MM`), `extracted_value` = `extracted_date`.
- `page-error`: `ledger_value`/`extracted_value` = null; the error string is in
  `description` (and optionally a `detail` key).

## Metadata shapes for EXISTING entry-level alerts (already written; now exposed)

| `type`                        | linkage keys in metadata               |
|-------------------------------|----------------------------------------|
| `duplicate_billing`           | `entry_ids` (list), `attachment_ids`   |
| `duplicate_entry`             | `entry_ids` (list)                     |
| `negative_credit`             | `entry_ids` (list)                     |
| `large_expense_no_attachment` | `entry_ids` (list)                     |

All other alert types (balance/subtotal/seasonality/vendor_concentration/category_growth/
delinquency/missing_period/new_vendor) have **no** entry/attachment linkage key → render no
links (FR-009).

## Derived UI shape

### `AttachmentMismatch` (Python dataclass, `scripts/analysis/mismatches.py`)
```
period: str
attachment_id: str
entry_id: str | None
kind: "amount" | "vendor" | "date" | "page-error"
ledger_value: float | str | None
extracted_value: float | str | None
detail: str | None         # page-error message
```
Consumed by both `summarize_mismatches` (→ terse CLI rows + `page_refs`) and
`check_attachment_mismatches` (→ `Alert` rows). Single source of truth (FR-004).

### `AlertRow` (TypeScript, `AlertsClient`) — add one field
```
metadata: string | null    // raw JSON; parsed client-side into { entryIds, attachmentIds, kind, ... }
```

### Deep link
`/dashboard/entries?period=<YYYY-MM>&entry=<entryId>` — see contracts/deep-link.md.
