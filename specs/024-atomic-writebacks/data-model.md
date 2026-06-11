# Phase 1 Data Model: Atomic delete-then-insert writebacks

No schema change (FR-008). This feature changes only **how** existing rows are written, not their
shape. The relevant existing entities and the write sequences they participate in:

## Entities (existing — read/written, unchanged shape)

### `attachment_analyses` (roll-up, one per attachment)
- Written by `_merge_and_write` via `upsert_tables` (now via the combined batch).
- Key: `id = det_id("attachment_analysis", attachment_id)`; FK `attachment_id`.

### `attachment_analysis_records` (per-page, many per analysis)
- Flattened out of the nested `analysis_records` by `d1.upsert_tables` / `build_sql` on write.
- FK `attachment_analysis_id`. Deleted-then-reinserted on every re-analysis.

### `attachments` (mirror table; analysis-owned column `classified_at`)
- Only `classified_at` is touched here (the analysis-owned stamp). The stamp now commits **with**
  the analysis insert, never with the delete alone.

### `alerts`
- Written delete-then-insert per `reference_period` and once globally for `type =
  'document_overpayment'`. Columns include user-disposition fields `resolved`, `resolved_at`,
  `notes` (preserved across re-runs by the existing graft logic — unchanged).

## Write sequences (the unit of atomicity)

| Scope | Statements (one submitted batch) | Atomic unit |
|-------|----------------------------------|-------------|
| One attachment analysis | `DELETE attachment_analysis_records WHERE analysis_id=…` ; `DELETE attachment_analyses WHERE attachment_id=…` ; `INSERT OR REPLACE attachment_analyses (+ flattened records)` ; `UPDATE attachments SET classified_at=<ms> WHERE id=…` | per attachment |
| One period's alerts | `DELETE alerts WHERE reference_period=…` ; `INSERT OR REPLACE alerts (rows)` (insert omitted when no rows) | per period |
| Overpayment alerts (global) | `DELETE alerts WHERE type='document_overpayment'` ; `INSERT OR REPLACE alerts (rows)` (insert omitted when no rows) | global |

**Invariant after the change**: each row in the table above is the result of a single transactional
batch — there is no observable state in which the `DELETE` has committed but the matching `INSERT`
(or the `classified_at` stamp) has not.

## State transitions — attachment classification

- **pending** (`classified_at IS NULL`) → **classified** (`classified_at = <ms>`): occurs **only**
  if the analysis insert in the same batch commits. On failure the attachment stays **pending**
  (self-healing — re-run re-attempts it).

## Helper (new) — `d1.upsert_sql(data) -> str`

- Pure function: returns the batched `INSERT OR REPLACE` SQL (`build_sql(data)[0]`) for `data`
  without executing it. Returns `""`/empty when `data` has no rows (caller then submits only its
  DELETE). `upsert_tables` is refactored to: `sql = upsert_sql(data); if sql: execute_sql(sql)`.
- No new state; deterministic over its input; same escaping/`TABLE_ORDER`/`PRAGMA` as today.
