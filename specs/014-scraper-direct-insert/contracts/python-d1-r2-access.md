# Contract: `scripts/common/d1.py` — wrangler-backed D1 + R2 access

The one new module. A thin, dependency-free wrapper that both the scraper and the analysis CLI use to read/write D1 and R2 against a chosen target. Replaces `import-to-d1.mjs` and `upload-images-to-r2.mjs`.

## Target

```python
Target = Literal["local", "remote"]   # resolved from a --remote flag; default "local"
```
- Maps to the `wrangler` `--local` / `--remote` flag.
- Every public function takes `target` explicitly (no hidden global).

## D1 writes

```python
def execute_sql(sql: str, *, target: Target) -> None
```
- Writes `sql` to a temp file and runs `npx wrangler d1 execute DATABASE --file=<tmp> [--local|--remote]` from the **repo root** (where `wrangler.toml` lives).
- Raises on non-zero exit (caller reports failure; FR-007).
- This is the escape hatch for any SQL that is **not** an upsert. In particular, the analysis writebacks issue their period-/document-scoped `DELETE`s through `execute_sql` before calling `upsert_tables` (delete-then-insert; see `period-loader-and-writeback.md` Writeback A & B) so stale rows from a prior run cannot survive. `upsert_tables` performs no deletes.

```python
def upsert_tables(data: dict[str, list[dict]], *, target: Target) -> dict[str, int]
```
- Builds one batched SQL document for a period's tables and executes it via `execute_sql`.
- Generation parity with `import-to-d1.mjs`:
  - iterate `TABLE_ORDER` (`scrape_runs, categories, vendors, units, subcategories, accountability_reports, entries, category_subtotals, approvers, documents, document_analyses, document_analysis_records, alerts`);
  - dedup rows by `id` per table;
  - flatten each `document_analyses[].analysis_records` into `document_analysis_records` (delete the nested key);
  - per row, `INSERT OR REPLACE INTO "<table>" (<cols>) VALUES (<vals>)` with columns derived from the row dict;
  - escape values: `None→NULL`, `int/float→str`, `bool→1|0`, `dict/list→'<json>'` (single-quotes doubled), else `'<str>'` (single-quotes doubled);
  - prepend `PRAGMA defer_foreign_keys = ON;`.
- Returns `{table: rows_written}` for the run summary (FR-005).

## D1 reads

```python
def query(sql: str, *, target: Target) -> list[dict]
```
- Runs `npx wrangler d1 execute DATABASE --command "<sql>" --json [--local|--remote]` and returns the result rows as dicts (parsing wrangler's JSON envelope — `[{ "results": [...] }]`).
- Used by the D1-backed loader (one or a few SELECTs per table, scoped by period).

## R2 objects

```python
def put_object(key: str, file_path: str, content_type: str, *, target: Target) -> None
def get_object(key: str, dest_path: str, *, target: Target) -> bool   # False if the object is absent
```
- `put_object`: `npx wrangler r2 object put "fiscal-documents/<key>" --file=<file_path> --content-type=<ct> [--local|--remote]`.
- `get_object`: `npx wrangler r2 object get "fiscal-documents/<key>" --file=<dest_path> [--local|--remote]`; returns `False` (not raise) when the key does not exist so analysis can skip/flag a missing page.
- Bucket name (`fiscal-documents`) and binding stay as in `wrangler.toml`.

## Behavioral contract

- **Default safety**: `target="local"` unless `--remote` was passed; callers print the resolved target before any remote write (SC-003).
- **Idempotency**: all writes are `INSERT OR REPLACE` / R2 overwrite — re-runs heal partial state (FR-006, FR-007).
- **No new deps**: uses `subprocess`, `json`, `tempfile`, `pathlib` only.
- **Auth**: remote operations use the operator's existing `wrangler` login; the module adds no credentials.
