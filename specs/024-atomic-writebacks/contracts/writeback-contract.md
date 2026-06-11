# Contract: Atomic writeback behavior

This is a behavioral contract over the Python analysis-pipeline writeback functions and the new
`common/d1.py` helper. There is no HTTP/REST surface — the "contract" is the observable behavior at
the `d1` seam and in D1 after a run.

## C1 — `common.d1.upsert_sql(data: dict[str, list[dict]]) -> str`

- **Given** a dataset dict (table → list of row dicts), **returns** the batched
  `INSERT OR REPLACE` SQL string that `build_sql(data)` produces (including its
  `PRAGMA defer_foreign_keys = ON;` header and per-table comments), **without executing it**.
- **Given** an empty/no-row dataset, **returns** an empty string `""` (so callers can detect
  "nothing to insert" and submit only their DELETE).
- `upsert_tables(data, target=…)` MUST be equivalent to: `sql = upsert_sql(data); if sql:
  execute_sql(sql, target=…)` — i.e. produce byte-identical executed SQL and the same `{table:
  count}` return as before.

## C2 — Attachment-analysis writeback (`_merge_and_write`)

- MUST submit **exactly one** `d1.execute_sql` call per attachment, whose SQL contains, in order:
  1. `DELETE FROM attachment_analysis_records WHERE attachment_analysis_id = '<aid>';`
  2. `DELETE FROM attachment_analyses WHERE attachment_id = '<did>';`
  3. the `INSERT OR REPLACE` SQL for `{"attachment_analyses": [result.to_dict()]}` (with its
     flattened per-page records), and
  4. `UPDATE attachments SET classified_at = <ms> WHERE id = '<did>';`
- MUST NOT issue the `classified_at` `UPDATE` in any batch that does not also contain the analysis
  `INSERT` (FR-002).
- On `execute_sql` failure (raised exception), MUST propagate it (FR-004) and MUST NOT have issued a
  separate committed delete (there is only the one batch).
- Successful result: the attachment holds exactly the new analysis + records (no stale records) and
  `classified_at` is set (FR-006).

## C3 — Per-period alerts writeback (`run_analysis` loop)

- For each period, MUST submit **exactly one** `d1.execute_sql` call whose SQL contains
  `DELETE FROM alerts WHERE reference_period = '<period>';` followed by the `INSERT OR REPLACE` SQL
  for the period's alert rows.
- When the period has **no** new alert rows, the single submitted SQL is just the `DELETE` (clears
  the scope to empty — FR-005).
- The resolution-preservation read + graft (`_read_existing_resolution` → `_graft_resolution`) MUST
  run before the batch is built, unchanged (FR-007).
- On failure, MUST propagate; the period's prior alerts remain intact (no committed standalone
  delete) (FR-003, US-1).

## C4 — Overpayment alerts writeback (global)

- MUST submit **exactly one** `d1.execute_sql` call whose SQL contains
  `DELETE FROM alerts WHERE type = 'document_overpayment';` followed by the `INSERT OR REPLACE` SQL
  for the overpayment rows (DELETE-only when there are no rows).
- Grafting of prior resolution (`overpayment_prior`) runs before the batch, unchanged.
- On failure, MUST propagate; prior overpayment alerts remain intact.

## C5 — No regressions

- No schema migration is introduced (FR-008).
- Executed INSERT SQL for every scope is byte-identical to the pre-change implementation (FR-006).
- Loud-failure behavior (non-zero `wrangler` exit → exception) is preserved (FR-004).
