# Data Model: Prune consumed and stale `page_classifications` staging rows

No schema change. This documents the tables involved and their lifecycle under the new cleanup.

## `page_classifications` (analysis-owned, staging) — existing, unchanged schema

| Column | Type | Notes |
|--------|------|-------|
| `id` | text PK | `det_id("page_classification", attachment_id, page_label)` |
| `attachment_id` | text | FK-like → `attachments.id`; the prune key |
| `page_label` | text | page identity within the attachment |
| `page_index` | int? | ordinal |
| `response` | text (JSON)? | the recorded fields object, or NULL for an error row |
| `error` | text? | error reason, or NULL for a fields row |
| `recorded_at` | int (ms) | write time |

**Lifecycle (new)**: a row is written by `record-classification` (INSERT OR REPLACE, latest wins),
and is now **deleted** when either:

1. its attachment's authoritative `attachment_analyses` write lands (consumed — apply), or
2. its attachment is re-queued via `mark-pending` (invalidated — start clean).

Plus the pre-existing cascade-clean on portal deletion (issue #35). The table therefore holds only
rows for not-yet-finalized, not-re-queued attachments.

## `attachment_analyses` / `attachment_analysis_records` (analysis-owned) — read context only

The successful INSERT of the per-attachment `attachment_analyses` row (inside `_merge_and_write`)
is the **trigger** for consuming that attachment's staging rows. No change to these tables.

## `attachment_state` (analysis-owned) — read context only

`mark-pending` clears `classified_at` here; the new behavior adds a staging-row delete to the same
batch. No schema change.

## Mirror tables (`entries`, `attachments`, `accountability_reports`) — untouched

The entry-id scope of `mark-pending` reads `attachments` (read-only subquery) to resolve attachment
ids; nothing in this feature writes a mirror table (FR-005).

## Derived helper

`_prune_page_classifications_sql(attachment_ids: list[str]) -> str`

- **Input**: a list of attachment ids (possibly empty).
- **Output**: `"DELETE FROM page_classifications WHERE attachment_id IN ('id1','id2',…);"` with each
  id single-quote-escaped (`'` → `''`); the empty string when the list is empty.
- **Purity**: no I/O; the caller folds the returned SQL into its own `execute_sql` batch.
