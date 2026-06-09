# Contract: D1-backed period loader + result writeback

The heart of the analysis refactor (plan slices 4 & 6). The single load seam flips from files to D1 while keeping its output shape frozen; the two writeback points flip from JSON to D1 upserts.

## Load — `scripts/analysis/loader.py:load_all_periods`

**Signature (unchanged)**:
```python
def load_all_periods(target: Target, periods_filter: list[str] | None = None
                     ) -> tuple[dict[str, PeriodData], RefIndex]
```
(`data_dir: str` parameter is replaced by `target: Target`; callers updated.)

**New behavior**: for each period (all, or those in `periods_filter`), query D1 and assemble the same per-period `raw` dict the old `<period>.json` held:

1. `SELECT * FROM accountability_reports [WHERE period IN (...)]` → group by period; skip periods with no report (same as today's warning).
2. For each period, `SELECT *` from the other ledger tables scoped to that period (entries/documents/subtotals/approvers via `report_id`/`period`; categories/vendors/units/subcategories via the ids referenced, or whole-table then filter in memory — whichever is simpler given table sizes).
3. `SELECT * FROM document_analyses` and `document_analysis_records` for the period; **re-nest** the records under their parent as `document_analyses[].analysis_records` so callers reading the nested array keep working.
4. `SELECT * FROM alerts` for the period.
5. Assemble `raw` with the canonical key set (see data-model.md), build `PeriodData`, and populate `RefIndex` (including `vendor_first_seen` computed across **all** periods, as today — query unfiltered for that one cross-period fact).

**Frozen output invariant**: the returned `(dict[str, PeriodData], RefIndex)` is byte-for-byte equivalent in shape to the JSON-era loader. This is the regression guard — every consumer downstream is untouched.

**Type coercion**: D1 returns SQLite-native types; the loader restores the dict shapes the pipeline expects (e.g. JSON columns like a record's `response` are parsed back to objects; `0|1` integer flags stay as-is, matching what the JSON held after import — verify against a parity period).

## Writeback A — `apply-extractions` (`extractions.py:_merge_and_write`)

**Before**: rewrites `<period>.json` with the merged `document_analyses`.
**After**: write the single document's analysis to D1 as **delete-then-insert**, reproducing the old "drop existing for this document_id, append" semantics:
1. `execute_sql("DELETE FROM document_analysis_records WHERE document_analysis_id = '<doc_analysis_id>'", target=...)`
2. `execute_sql("DELETE FROM document_analyses WHERE document_id = '<document_id>'", target=...)`
3. `upsert_tables({"document_analyses": [result.to_dict()]}, target=...)` (flattens `analysis_records` into `document_analysis_records`).

Plain `INSERT OR REPLACE` alone is **not** sufficient: it only replaces rows whose ids match, so if a re-analysis produces fewer pages (or a different NF grouping changes the representative), the prior per-page `document_analysis_records` rows would be **orphaned**. The leading deletes remove them. (The JSON-era code avoided this implicitly by rewriting the whole period array.)

## Writeback B — `analyze` (`__init__.py:run_analysis`)

**Before**: sets `period_data.raw["alerts"]` and rewrites `<period>.json`.
**After**: alerts are fully recomputed each run, so use delete-then-insert per period: `execute_sql("DELETE FROM alerts WHERE <period-scope>", target=...)` then `upsert_tables({"alerts": [...]}, target=...)`. This guarantees no stale alert from a prior run survives (a plain upsert would leave alerts that the new run no longer emits). Scope the delete by the period's `report_id`/`period` column as the schema allows.

## Parity test (verification, not code)

Pick an existing period currently in D1 (imported via the old path). Run the new analysis loader against it and assert the assembled `raw` matches the legacy JSON for that period (same counts and key values for entries/documents/analyses/alerts). This proves SC-002/SC-005 before the old path is removed.
