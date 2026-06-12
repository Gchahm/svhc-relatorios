# Data Model: Shared alert type → label map

No persisted data. No D1 table, no migration, no schema change. This feature is a pure presentation
helper over the existing in-memory `type: string` field already present on alert rows.

## Conceptual entities

- **Alert type** (`string`): the machine identifier already carried on each alert row
  (`alerts.type` in D1, surfaced as `AlertRow.type` in the client). Input to the mapping. Not
  modified by this feature.
- **Type label** (`string`): the human-readable string returned for a given alert type. Derived,
  never stored.

## Mapping (curated)

| type | label |
|------|-------|
| `attachment_amount_mismatch` | Attachment amount mismatch |
| `attachment_vendor_mismatch` | Attachment vendor mismatch |
| `attachment_date_mismatch` | Attachment date mismatch |
| `attachment_page_error` | Attachment page error |
| `attachment_not_downloaded` | Attachment not downloaded |
| `document_overpayment` | Document overpayment |
| `duplicate_billing` | Duplicate billing |
| `duplicate_entry` | Duplicate entry |
| `negative_credit` | Negative credit |
| `large_expense_no_attachment` | Large expense without attachment |
| `unit_delinquency` | Unit delinquency |
| `subtotal_mismatch` | Subtotal mismatch |
| `balance_opening_mismatch` | Opening balance mismatch |
| `balance_month_mismatch` | Month balance mismatch |
| `balance_accumulated_mismatch` | Accumulated balance mismatch |
| `entries_revenue_mismatch` | Entries vs. revenue mismatch |
| `entries_expenses_mismatch` | Entries vs. expenses mismatch |
| `portal_row_vanished` | Portal row vanished |
| `scrape_inconsistency` | Scrape inconsistency |
| `new_vendor` | New vendor |
| `vendor_concentration` | Vendor concentration |
| `category_growth_outlier` | Category growth outlier |
| `subcategory_above_average` | Subcategory above average |
| `missing_recurring_subcategory` | Missing recurring subcategory |
| `missing_period` | Missing period |

## Fallback rule

Any type not in the table above → `type.replace(/_/g, " ")` then capitalize the first character
(sentence case); empty string → empty string. Never throws.
