# Contract: staging-row pruning

This feature has no HTTP/API surface. The contracts are the internal SQL-helper signature and the
two batch-composition behaviors.

## `_prune_page_classifications_sql(attachment_ids) -> str`

Module: `scripts/analysis/page_classifications.py`

```python
def _prune_page_classifications_sql(attachment_ids: list[str]) -> str: ...
```

| Case | Input | Output |
|------|-------|--------|
| empty | `[]` | `""` |
| single | `["a"]` | `"DELETE FROM page_classifications WHERE attachment_id IN ('a');"` |
| multiple | `["a", "b"]` | `"DELETE FROM page_classifications WHERE attachment_id IN ('a','b');"` |
| escaping | `["o'brien"]` | `"...WHERE attachment_id IN ('o''brien');"` |

- MUST NOT execute anything (pure string builder).
- MUST single-quote-escape each id (`'` → `''`).
- Output, when non-empty, MUST end with `;` so it composes cleanly between other statements in a
  batch.

## Apply consume (FR-001, FR-002, FR-006)

Module: `scripts/analysis/attachments.py` — `_merge_and_write`

The single `execute_sql` batch MUST, after the `attachment_analyses` INSERT (and the
`attachment_state` stamp), include `_prune_page_classifications_sql([result.attachment_id])`.

- The DELETE MUST be scoped to exactly `result.attachment_id` (FR-006).
- Because it is in the same `execute_sql` string, it commits/rolls back atomically with the insert
  (FR-002): a raised `CalledProcessError` leaves both the analysis and the staging rows unwritten.
- For a sibling attachment (no staging rows of its own) the DELETE matches zero rows — a harmless
  no-op.

## Re-queue invalidate (FR-003, FR-004)

Module: `scripts/analysis/extractions.py` — `mark_pending`

When at least one of `attachment_ids` / `entry_ids` is given, the single `execute_sql` batch MUST
contain BOTH:

1. the existing `UPDATE attachment_state SET classified_at = NULL WHERE <clauses>;`, and
2. a `DELETE FROM page_classifications WHERE <same id scope>;`

where `<id scope>` covers the attachment-id list literally AND the entry-id list via the existing
read-only subquery `attachment_id IN (SELECT id FROM attachments WHERE entry_id IN (…))`.

- With NO ids given, `mark_pending` MUST remain a no-op and return 0 (FR-004) — no UPDATE, no DELETE.
- The return value (count of requested ids) is unchanged.
