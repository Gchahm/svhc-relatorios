# Contract: Shared per-attachment mismatch detection

## Module: `scripts/analysis/mismatches.py` (NEW, stdlib only)

```python
KIND_AMOUNT = "amount"
KIND_VENDOR = "vendor"
KIND_DATE = "date"
KIND_PAGE_ERROR = "page-error"

@dataclass
class AttachmentMismatch:
    period: str
    attachment_id: str
    entry_id: str | None
    kind: str                       # one of the KIND_* constants
    ledger_value: float | str | None
    extracted_value: float | str | None
    detail: str | None = None       # page-error message

def detect_attachment_mismatches(period: PeriodData, refs: RefIndex) -> list[AttachmentMismatch]:
    ...
```

### Detection rules (read persisted `attachment_analyses`)

For each analysis `a` in `period.raw["attachment_analyses"]`, resolve its entry via
`attachments[a.attachment_id].entry_id`:
- `a.error` set → one `page-error` mismatch (`detail = a.error`); skip the rest for that `a`.
- else `a.amount_match == 0` → `amount` (`ledger_value = entry.amount`,
  `extracted_value = a.extracted_amount`).
- else/and `a.vendor_match == 0` → `vendor` (`ledger_value = refs.vendor_name(entry.vendor_id)`,
  `extracted_value = a.issuer_name`).
- and `a.date_match == 0` → `date` (`ledger_value = period`, `extracted_value = a.extracted_date`).

A single attachment may yield multiple mismatches (amount + vendor + date), but at most one
per kind. Reconciliation is already baked into the persisted match flags (no recompute).

## Consumers

### `extractions.summarize_mismatches` (EDIT)
Builds its per-attachment terse rows from `detect_attachment_mismatches(...)`, then adds
`page_refs` and applies the `attachment_id`/`entry_id` scoping filters. **Output row shape is
unchanged** (`kind`, `ledger_amount`/`extracted_amount`, `ledger_vendor`/`extracted_issuer`,
`expected_period`/`extracted_date`, `detail`, `page_refs`) — the loop/review worker contract
is preserved. The `duplicate_billing` rows (derived from alerts, not analyses) are unchanged.

### `checks/attachments.py:check_attachment_mismatches(period, refs)` (NEW)
Maps each `AttachmentMismatch` to an `Alert`:
- `type`: `attachment_amount_mismatch` | `attachment_vendor_mismatch` |
  `attachment_date_mismatch` | `attachment_page_error`.
- `severity`: `info` for page-error, else `warning`.
- `discriminator`: `attachment_id` (id = `det_id("alert", period, type, attachment_id)`).
- `metadata`: `{ attachment_id, entry_id, kind, ledger_value, extracted_value }`
  (+ `detail` for page-error).
- `title`/`description`: human-readable pt-BR, consistent with existing alerts.

Wired into `run_all_checks` (via `run_advanced`, alongside `check_duplicate_billing`) so it
runs for every period and writes through the existing delete-then-insert path → idempotent
(FR-003).

## Invariant (SC-004)

For any period, the count of `amount`/`vendor`/`date`/`page-error` rows from `mismatches`
equals the count of `attachment_*_mismatch`/`attachment_page_error` alerts from `analyze`
(both derive from `detect_attachment_mismatches`).
