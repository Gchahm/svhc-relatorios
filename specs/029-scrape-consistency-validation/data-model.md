# Phase 1 Data Model: Scrape-time consistency validation

No persisted schema change. This feature reads in-memory period data and existing rows, and writes only the existing `alerts` table + the existing `scrape_runs.errors` text field.

## In-memory inputs (already produced by the scraper)

From the per-period payload (`period_data`) built in `_scrape_periodo` and the demonstrativo dict:

- **entries** — list of `{id, subcategory_id, amount, movement_type, ...}` (mirror rows).
- **category_subtotals** — list of `{id, subcategory_id, amount, movement_type, ...}`.
- **demonstrativo totals** — `total_receitas` (float), `total_despesas` (float), carried on the `report` dict as `total_revenue` / `total_expenses`.

## Pure-module data shapes (`scripts/scraper/consistency.py`)

### `Discrepancy` (dataclass)
One failing comparison.
- `level: str` — `"subcategory"` or `"demonstrativo"`.
- `movement_type: str` — `"C"` or `"D"`.
- `subcategory_id: str | None` — set for `level == "subcategory"`, else `None`.
- `computed_sum: float` — the sum computed from the more-granular side (entry-sum for subcategory level; subtotal-sum for demonstrativo level).
- `reported_total: float` — the side it is checked against (the recorded subtotal; or the demonstrativo total).
- `difference: float` — `round(computed_sum - reported_total, 2)`.

### `ConsistencyResult` (dataclass)
- `discrepancies: list[Discrepancy]` — empty ⇒ consistent.
- `affected_entry_ids: list[str]` — sorted union of entry ids belonging to any subcategory `(subcategory_id, movement_type)` key that failed the subcategory-level check (empty when only demonstrativo-level failed).
- `sql: str` — the ONE batch SQL string (see contracts): always a `DELETE FROM "alerts" WHERE "id" = <id>;`, followed (only when `discrepancies` non-empty) by `INSERT OR REPLACE INTO "alerts" (...) VALUES (...);`.
- `alert: dict | None` — the alert row dict that was rendered into the INSERT (None when consistent), so the runner can log/summary from it.
- `summary: str | None` — a one-line human summary for the run-log warning + the `scrape_runs.errors` note (None when consistent).

## Detection rules

1. **Subcategory-level**: build `entry_sums[(subcategory_id, movement_type)] = round(sum(amount), 2)` over entries; build `subtotal_amounts[(subcategory_id, movement_type)] = amount` over category_subtotals (the source already consolidates one row per key). For each key in the union of both maps, let `computed = entry_sums.get(key, 0.0)` and `reported = subtotal_amounts.get(key, 0.0)`; if NOT `within_tolerance(computed, reported)` → a `subcategory` `Discrepancy`.
2. **Demonstrativo-level**: `c_sum = round(sum(subtotal amounts where movement_type == "C"), 2)`, `d_sum = round(sum(... == "D"), 2)`. If NOT `within_tolerance(c_sum, total_receitas)` → a `demonstrativo`/`C` discrepancy; same for `d_sum` vs `total_despesas` → `demonstrativo`/`D`.

`within_tolerance(value, reference)`: `abs(value - reference) <= AMOUNT_ABS_TOL` OR (`reference > 0` and `abs(value - reference)/reference < AMOUNT_REL_TOL`), with `AMOUNT_ABS_TOL = AMOUNT_REL_TOL = 0.05` (mirrors `nf_groups.within_tolerance`).

## Alert row (existing `alerts` table)

- `id` = `det_id("alert", period, "scrape_inconsistency")` — stable per period (idempotent re-scrape).
- `created_at` = `now_ms()`.
- `type` = `"scrape_inconsistency"`.
- `severity` = `"warning"`.
- `title` = e.g. `"Ledger does not reconcile — <period> (<n> discrepancy/ies)"`.
- `description` = human text naming the layers that failed and the largest disagreement.
- `reference_period` = `period`.
- `resolved` / `resolved_at` / `notes` = `0` / `NULL` / `NULL` by default, **grafted** from the prior alert's disposition when present (mirrors `reconcile._graft_resolution`).
- `metadata` = JSON: `{ "entry_ids": [...], "checks": [ {level, movement_type, subcategory_id?, computed_sum, reported_total, difference}, ... ], "counts": {"subcategory": x, "demonstrativo": y} }`.

## `scrape_runs.errors` interaction

`run_scrape` sets `scrape_run["status"] = "error" if errors else "success"` and writes `scrape_run["errors"]` in the `finally`. A consistency mismatch is NOT a fatal scrape error and MUST NOT flip `status` to `error`. So the runner keeps a **separate** `consistency_notes` list; the per-period summary line is appended there (and logged as a `warning`). In the `finally`, `scrape_run["errors"]` is composed from `errors + consistency_notes` (joined) so the mismatch is queryable on the run row, while `status` is still driven only by the fatal `errors` list. (If `errors` is empty but `consistency_notes` is non-empty, `status` stays `success` and `errors` carries the consistency note text.)
