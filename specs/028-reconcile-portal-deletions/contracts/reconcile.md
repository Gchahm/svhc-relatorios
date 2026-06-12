# Contract: `scripts/scraper/reconcile.py`

A pure, stdlib-only, playwright-free module (mirrors `scripts/scraper/preserve.py`). It builds the
reconciliation SQL batch + alert payload from already-fetched data; it performs **no** I/O. The
impure reads/execute live in `runner.py`.

## Public surface

```python
@dataclass
class ReconcileResult:
    sql: str                 # full batch SQL ("" only when there is literally nothing to do —
                             #   i.e. nothing stale AND no prior alert to clear is being forced)
    deleted_counts: dict[str, int]   # {"entries": n, "attachments": n, "category_subtotals": n,
                                     #  "approvers": n} — stale rows removed
    alert: dict | None       # the alerts row dict to INSERT, or None when nothing vanished

def build_reconciliation(
    period: str,
    existing: ExistingRows,      # rows read from D1 for the period (see below)
    scraped: ScrapedIds,         # id sets from the period_data just upserted
) -> ReconcileResult: ...
```

### `existing` (read from D1 in `runner.py`)

```python
@dataclass
class ExistingRows:
    entries: list[dict]          # each: {id, date, description, amount}
    attachments: list[dict]      # each: {id, entry_id}
    subtotal_ids: set[str]
    approver_ids: set[str]
```

### `scraped` (from the in-memory period payload)

```python
@dataclass
class ScrapedIds:
    entry_ids: set[str]
    attachment_ids: set[str]
    subtotal_ids: set[str]
    approver_ids: set[str]
```

## Behavior contract

1. **Diff** computes `stale_entry_ids`, `stale_attachment_ids` (set difference ∪ attachments owned
   by a stale entry), `stale_subtotal_ids`, `stale_approver_ids` per the data-model.
2. **No-op**: if nothing is stale, `build_reconciliation` returns
   `ReconcileResult(sql=<DELETE-stale-alert-only>, deleted_counts=all-zero, alert=None)`. The
   caller still runs that DELETE so a prior period alert clears when deletions are reverted; if the
   caller wants to skip the DB round-trip entirely it MAY check `deleted_counts` + `alert is None`
   and only execute when `sql` is non-empty. (The always-clear DELETE is cheap; keeping it makes the
   alert truly idempotent.)
3. **SQL** is a single string beginning with `PRAGMA defer_foreign_keys = ON;`, containing the
   cascade DELETEs (only for non-empty id sets), the `DELETE FROM alerts WHERE
   type='portal_row_vanished' AND reference_period=<p>`, and — when something is stale — the
   `INSERT OR REPLACE INTO alerts (...)` row. All id-list literals are SQL-escaped (single quotes
   doubled); empty id sets emit no statement for that table.
4. **Alert** (when stale) is the dict in data-model.md; `alert is None` otherwise.
5. **Scoping**: every DELETE is constrained to the stale id sets or the period — never matches
   surviving rows or other periods (FR-005). The module receives only this period's data, so it
   cannot touch another period.
6. **Purity**: no `subprocess`, no `d1` import that executes — it MAY import `common.det_id` /
   `common.now_ms` (pure helpers) and the SQL-escape helper, but it never calls wrangler.

## Caller contract (`runner.py`)

After `d1.upsert_tables(period_data)` succeeds for a period:

1. Build `ScrapedIds` from `period_data`.
2. `d1.query(...)` the four `ExistingRows` sets for the period (`target` threaded).
3. `result = build_reconciliation(period, existing, scraped)`.
4. If `result.sql`: `d1.execute_sql(result.sql, target=target)` (one batch) and log
   `result.deleted_counts` + whether an alert fired.
5. Reconciliation runs ONLY on the scrape-success path (FR-008); a failed/retried period never
   reaches this code.

## Test contract (`scripts/tests/test_reconcile.py`, stdlib `unittest`)

- `test_noop_when_identical`: existing == scraped → `deleted_counts` all zero, `alert is None`, sql
  is the clear-only DELETE (no INSERT, no entry/attachment DELETE).
- `test_stale_entry_diffed`: one existing entry absent from scraped → it's in `stale_entry_ids`;
  sql contains a `DELETE FROM "entries" ... WHERE "id" IN ('E3')` and the alert metadata lists E3's
  frozen values.
- `test_stale_entry_cascades_attachment`: a stale entry's attachment is included in
  `stale_attachment_ids` even if the scrape still listed the attachment id (entry-gone wins), and the
  sql deletes the five dependents for it.
- `test_independent_stale_attachment`: an attachment absent from scraped whose entry survives is
  still cascade-cleaned.
- `test_atomic_single_batch`: sql is ONE string, starts with the defer-FK pragma, and contains the
  alerts DELETE + INSERT (no separate execute implied).
- `test_alert_idempotent_id`: alert `id == det_id("alert", period, "portal_row_vanished")` and the
  sql always DELETEs that period's prior `portal_row_vanished` before inserting.
- `test_subtotals_and_approvers_diffed`: stale subtotal/approver ids produce their DELETEs and bump
  `deleted_counts`.
- `test_surviving_rows_untouched`: ids present in both sets never appear in any DELETE id-list.
- `test_escaping`: an id/description containing a single quote is doubled in the SQL.
