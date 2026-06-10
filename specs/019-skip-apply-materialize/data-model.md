# Data Model: Skip R2 image materialization in apply-extractions

**Feature**: 019-skip-apply-materialize | **Date**: 2026-06-10

No schema changes. This feature reads existing fields only; no migration. The "model" here is the
in-memory shape the guard inspects.

## Entities (existing, read-only)

### Attachment (`attachments` table, in-memory `doc` dict)

Relevant fields the guard reads:

| Field | Type | Meaning for this feature |
|-------|------|--------------------------|
| `id` | text (UUID) | Identifies the attachment; the unit the guard scopes materialization by. |
| `file_path` | text (`;`-joined R2 keys, may be empty/NULL) | Page-bearing iff non-empty after trimming. Empty → page-less → never hashable. |
| `content_hash` | text (may be NULL) | Shared-NF grouping key, written at scrape time (feature 021). NULL on legacy/edge rows. |
| `classified_at` | int ms (may be NULL) | Pending-set marker. **Not** part of the guard set (grouping spans all page-bearing rows, not just pending). |

### Derived set: "hashable-unhashed"

Not persisted — computed per run from the loaded periods:

```
needing = { doc.id
            for pd in periods.values()
            for doc in pd.attachments
            if non_empty(doc.file_path) and not doc.content_hash
            and (attachment_ids is None or doc.id in attachment_ids) }
```

- **Empty set** (normal case): every page-bearing attachment already has a `content_hash` →
  apply skips materialization entirely; grouping reads the column.
- **Non-empty set**: those ids are materialized (scoped) and their `content_hash` is computed in
  memory + backfilled to D1 by `materialize_period_images(..., backfill_hash=True)`.

## State transition (a single legacy attachment)

```
content_hash = NULL, file_path = "2025-12/x_p1.png"
        │  (apply run: in `needing` set → materialize scoped → hash from files)
        ▼
content_hash = <sha>  (mutated in memory this run; grouping uses it)
        │  (best-effort D1 UPDATE … WHERE content_hash IS NULL)
        ▼
content_hash = <sha> persisted  → future apply runs find it keyed → no materialization
```

Self-correcting: convergence requires no manual action (FR-007).

## Invariants

- **INV-1**: A page-less attachment (`file_path` empty) is never in the `needing` set, regardless of
  `content_hash` (FR-004).
- **INV-2**: When `needing` is empty, `apply_extractions` performs zero R2 `get_object` calls
  (FR-001, SC-001).
- **INV-3**: Grouping output (`group_attachments`) is identical whether materialization ran or not,
  because already-keyed rows group from the column and newly-keyed rows get the same hash the
  fallback would have computed (FR-005).
