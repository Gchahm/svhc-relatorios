# Contract: apply-extractions materialization guard

**Feature**: 019-skip-apply-materialize | **Date**: 2026-06-10

This is a Python-internal contract (no HTTP/REST surface). It defines the new predicate and the
guarded behavior of `apply_extractions`.

## New function: `attachments_needing_hash_backfill`

**Location**: `scripts/analysis/images.py`

```python
def attachments_needing_hash_backfill(
    periods: dict,
    attachment_ids: list[str] | None = None,
) -> list[str]:
    """Return the in-scope attachment ids that genuinely need an image fetch for a
    content_hash backfill: page-bearing (non-empty file_path) AND missing content_hash.

    A page-less attachment (empty file_path) is never included — it has no hash by nature
    and groups as a singleton. When ``attachment_ids`` is given, only those ids are considered.
    """
```

**Behavior table**:

| Attachment state | In returned list? |
|------------------|-------------------|
| `file_path` non-empty, `content_hash` set | No |
| `file_path` non-empty, `content_hash` NULL/empty | Yes |
| `file_path` empty/NULL, `content_hash` NULL | No (page-less, not hashable) |
| out of `attachment_ids` scope (when provided) | No |

**Guarantees**:
- Pure read of the in-memory `periods` dict; no D1/R2 access, no mutation.
- Order: deterministic (iteration order of `periods` then `pd.attachments`).

## Guarded behavior: `apply_extractions`

**Location**: `scripts/analysis/extractions.py`

```python
needing = attachments_needing_hash_backfill(periods)
if needing:
    materialize_period_images(periods, cache_dir, target, attachment_ids=needing)
else:
    logger.info("All page-bearing attachments already have content_hash; "
                "skipping R2 image materialization")
```

**Contract**:
- **C-1 (skip)**: when `needing == []`, `materialize_period_images` is NOT called → zero R2
  `get_object` calls in the apply path. (FR-001)
- **C-2 (backfill)**: when `needing != []`, `materialize_period_images` is called scoped to exactly
  those ids with the default `backfill_hash=True`, so their images are fetched, hashed, and
  `content_hash` is backfilled. (FR-002, FR-003)
- **C-3 (parity)**: the subsequent `build_plan` / roll-up / reconciliation / fan-out / write-back
  is unchanged; for the same input the written `attachment_analyses` and match flags are identical
  to the prior always-materialize behavior. (FR-005)
- **C-4 (isolation)**: `materialize_period_images` itself is unchanged; `plan_extractions` /
  `build_plan` and `summarize_mismatches` still materialize as before. (FR-006)

## Out of scope

- No new CLI command, no flag changes to `apply-extractions`, no schema/migration. (FR-008 covers
  docs only.)
