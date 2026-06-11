# Contract: attachment_state read/write seam

This feature has no HTTP/API surface (analysis-internal). The "contracts" are the behavioral
guarantees of the pipeline seams that read/write classification state. Each is verifiable against
local D1.

## C1 — Loader supplies `classified_at` from `attachment_state`

**Seam**: `scripts/analysis/loader.py` attachment query.

- **Given** an attachment with a state row `classified_at = T`, **then** the attachment dict
  returned by the loader has `classified_at == T`.
- **Given** an attachment with no state row (or `classified_at IS NULL`), **then** the attachment
  dict has `classified_at` is `None`.
- **Invariant**: the loader query MUST NOT select `classified_at` from `attachments` (the column
  is gone); it comes via `LEFT JOIN attachment_state s ON s.attachment_id = d.id`.

## C2 — `select_work` pending semantics unchanged

**Seam**: `scripts/analysis/attachments.py:select_work`.

- **Given** a page-bearing attachment whose dict `classified_at is None`, **then** it is included
  in the work set (pending).
- **Given** a page-bearing attachment whose dict `classified_at is not None`, **then** it is
  excluded (classified).
- The code reading `doc.get("classified_at")` is unchanged; only its source (C1) moved.

## C3 — Classified stamp is atomic and targets `attachment_state`

**Seam**: `scripts/analysis/attachments.py:_merge_and_write`.

- The single `execute_sql` batch MUST contain, in order: the two analysis DELETEs, the
  `attachment_analyses` INSERT, and an upsert into `attachment_state` setting
  `classified_at = <now_ms>` for the attachment id — and MUST contain **no** statement touching
  `attachments`.
- **Given** the batch fails, **then** no `attachment_state` row is left with a non-NULL
  `classified_at` for that attachment (atomic rollback → still pending; FR-004).

## C4 — `mark-pending` returns to pending via `attachment_state`

**Seam**: `scripts/analysis/extractions.py:mark_pending`.

- **Given** a classified attachment, **when** `mark-pending` runs for it, **then** its state row's
  `classified_at` becomes NULL and the next `select_work` treats it as pending.
- The statement MUST target `attachment_state` only; it MUST NOT write `attachments`.
- An attachment with no state row needs no action (already pending) — clearing only matches
  existing rows; this is acceptable (FR-005).

## C5 — Analysis issues zero writes to `attachments`

**Seam**: whole analysis pipeline (`apply-extractions`, `mark-pending`, image materialization).

- **Given** a full classify → apply → analyze → mismatches run over a period (including a legacy
  attachment with `content_hash IS NULL`), **then** the count of `attachments`-targeting
  write statements (INSERT/UPDATE/DELETE) emitted by the analysis pipeline is **zero** (FR-002,
  SC-001). The `content_hash` for a NULL row is computed in memory for this run's grouping only —
  not persisted.

## C6 — Grouping unchanged

**Seam**: `scripts/analysis/nf_groups.py:group_attachments` (unchanged code).

- **Given** a period, **then** the shared-NF groups are identical to pre-change, including for
  attachments whose `content_hash` column is NULL (the in-memory compute-from-cache fallback fills
  it for grouping). (SC-004)

## Verification matrix

| Contract | Verified by |
|----------|-------------|
| C1, C2   | `scripts/tests/test_attachment_state.py` (loader/select_work fixtures) + local-D1 `docs-plan` shows expected pending set |
| C3       | unit test asserting the `_merge_and_write` SQL string shape (one batch, targets `attachment_state`, no `attachments`) |
| C4       | unit test + local-D1: `mark-pending` an id, re-run `docs-plan`, see it pending again |
| C5       | grep/assert no `attachments` write in analysis SQL; local-D1 row-hash before/after a full run is identical |
| C6       | local-D1: groups + reconciliation outcomes equal before/after |
