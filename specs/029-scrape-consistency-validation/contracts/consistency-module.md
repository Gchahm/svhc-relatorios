# Contract: `scripts/scraper/consistency.py` (pure module)

Stdlib-only. No `playwright`, no D1, no `scripts/analysis` import. Performs NO I/O — builds the result + SQL from already-fetched data. Unit-tested directly (`scripts/tests/test_scrape_consistency.py`).

## Constants

```python
AMOUNT_REL_TOL = 0.05   # mirrors scripts/analysis/nf_groups.py:within_tolerance
AMOUNT_ABS_TOL = 0.05
ALERT_TYPE = "scrape_inconsistency"
ALERT_SEVERITY = "warning"
```

## Functions

```python
def within_tolerance(value: float, reference: float) -> bool:
    """True when value matches reference within abs OR relative band."""

def detect_inconsistencies(
    entries: list[dict],            # each: {id, subcategory_id, amount, movement_type}
    category_subtotals: list[dict], # each: {subcategory_id, amount, movement_type}
    total_receitas: float,
    total_despesas: float,
) -> tuple[list[Discrepancy], list[str]]:
    """Return (discrepancies, affected_entry_ids). Pure; no I/O."""

def build_consistency_writeback(
    period: str,
    entries: list[dict],
    category_subtotals: list[dict],
    total_receitas: float,
    total_despesas: float,
    prior_resolution: dict | None = None,   # {resolved, resolved_at, notes} read from D1 by the caller
) -> ConsistencyResult:
    """Detect + build the one-batch SQL + alert dict + summary. Pure; no I/O."""
```

## SQL batch contract (`ConsistencyResult.sql`)

- ALWAYS first statement: `DELETE FROM "alerts" WHERE "id" = '<det_id>';` (clears a prior per-period alert — makes a now-consistent re-scrape clear the stale finding, FR-005).
- WHEN inconsistent: append `INSERT OR REPLACE INTO "alerts" ("id", "created_at", "type", "severity", "title", "description", "reference_period", "resolved", "resolved_at", "notes", "metadata") VALUES (...);` with values escaped exactly as `reconcile._sql_str` does (single quotes doubled; `None`→`NULL`; bool→`1`/`0`; dict/list→JSON string).
- The two statements are submitted to D1 in ONE `execute_sql` call by the caller (atomic — FR-009). When consistent, the batch is the lone DELETE (idempotent clear).

## Resolution graft

`build_consistency_writeback` applies `prior_resolution` to the alert (only when inconsistent) exactly like `reconcile._graft_resolution`: if the prior row has `resolved` truthy OR `notes` non-empty, copy `resolved`/`resolved_at`/`notes` onto the new alert; else keep the unresolved default (FR-008). `resolved` coerced via `int(... or 0)`.

## Caller contract (`scripts/scraper/runner.py`)

A new `_check_consistency(period, period_data, report, target) -> str | None` (impure):
1. `alert_id = det_id("alert", period, ALERT_TYPE)`; read `prior_resolution` via `d1.query("SELECT resolved, resolved_at, notes FROM alerts WHERE id = '<alert_id>'", target)`.
2. `result = build_consistency_writeback(period, period_data["entries"], period_data["category_subtotals"], report["total_revenue"], report["total_expenses"], prior_resolution)`.
3. `d1.execute_sql(result.sql, target=target)` (one batch).
4. If `result.discrepancies`: `logger.warning("  Consistency mismatch in %s: %s", period, result.summary)` and `return result.summary`; else `logger.info("  Consistency OK for %s", period)` and `return None`.

`run_scrape` collects the returned summary (when non-None) into a `consistency_notes` list and, in `finally`, composes `scrape_run["errors"]` from `errors + consistency_notes` WITHOUT letting `consistency_notes` flip `status` to `error`.
