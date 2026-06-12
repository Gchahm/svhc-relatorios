# Research: Prune consumed and stale `page_classifications` staging rows

No `NEEDS CLARIFICATION` markers remained after specify/clarify. This records the design
decisions and the existing-code facts they rest on.

## Decision 1: Consume on apply via the existing atomic `_merge_and_write` batch

- **Decision**: Append a `DELETE FROM page_classifications WHERE attachment_id = '<id>'` to the
  single `execute_sql` batch already built by `_merge_and_write` (`scripts/analysis/attachments.py`),
  so the staging-row delete commits in the same D1 implicit transaction as the
  `attachment_analyses` insert + `attachment_state` stamp.
- **Rationale**: `_merge_and_write` already folds two DELETEs + the analysis INSERT + the
  `attachment_state` upsert into one `execute_sql` call (feature 024 / issue #37). Adding the
  staging DELETE to that same string gives FR-002 (atomicity) for free: a failed write rolls back
  the whole batch, so the staging rows survive and the attachment stays pending (no
  `attachment_state` stamp), self-healing on re-run. It also avoids any extra `wrangler` round trip
  on the hot apply path (one batch per attachment, as today).
- **Alternatives considered**:
  - *Separate `execute_sql` after the write* — rejected: two calls break atomicity (FR-002); a
    crash between them could delete staging rows after a write or, worse, before confirming it.
  - *Prune-by-validity (issue suggestion 2: delete only rows whose `page_label` is not in the
    current `file_path`)* — rejected: once the attachment's analysis lands, ALL of its staging rows
    are obsolete (frozen into the analysis), so a blanket per-attachment delete is simpler and also
    sweeps any stale leftover page rows. Validity pruning is strictly weaker.

## Decision 2: A pure SQL-returning helper shared by both callers

- **Decision**: Add `_prune_page_classifications_sql(attachment_ids: list[str]) -> str` to
  `scripts/analysis/page_classifications.py`. Returns a single
  `DELETE FROM page_classifications WHERE attachment_id IN ('a','b',…);` statement, or `""` for an
  empty id list. Quote-escapes ids the same way the codebase does (`.replace("'", "''")`).
- **Rationale**: Mirrors the `upsert_sql` seam (return SQL without executing, so callers fold it
  into their own batch) and the `_prune_sql` pattern in `scripts/analysis/documents.py`. One pure
  function is unit-testable without a live D1 and is reused by both hooks (DRY, FR-007).
- **Alternatives considered**:
  - *Inline the SQL at both call sites* — rejected: duplicated escaping logic, two places to keep
    in sync; a shared helper is the project convention.
  - *A `delete_page_classifications(...)` that executes itself* — rejected: it couldn't be folded
    into `_merge_and_write`'s atomic batch (FR-002), and `mark_pending` already builds its own SQL
    string.

## Decision 3: `mark_pending` prunes in its own batch

- **Decision**: In `mark_pending` (`scripts/analysis/extractions.py`), after computing the matched
  attachment ids (attachment-id scope is literal; entry-id scope resolves via the existing read-only
  `SELECT id FROM attachments WHERE entry_id IN (…)` subquery), append the prune DELETE to the same
  `execute_sql` that clears `attachment_state.classified_at`.
- **Rationale**: `mark_pending` already issues one `execute_sql`
  (`UPDATE attachment_state SET classified_at = NULL WHERE …`). Folding the staging DELETE into the
  same call keeps it one batch (atomic re-queue: state cleared and staging cleared together). For
  the entry-id scope, the DELETE reuses the identical `attachment_id IN (SELECT id FROM attachments
  WHERE entry_id IN (…))` subquery the UPDATE uses — no new mirror write (the SELECT is read-only).
- **Alternatives considered**:
  - *Resolve entry ids to attachment ids in Python first* — rejected: would add a `query()` round
    trip and diverge from how the UPDATE already scopes itself; reusing the SQL subquery is simpler
    and keeps the two clauses consistent.

## Decision 4: No global orphan-sweep command (issue suggestion 3 partially)

- **Decision**: Do not add a standalone "delete all orphaned staging rows" command.
- **Rationale**: The two hooks (apply consumes, `mark-pending` invalidates) plus the scraper's
  existing portal-deletion cascade (issue #35 — `_reconcile_period` already cascade-cleans
  `page_classifications` for a removed attachment) cover every identified accumulation source. A
  sweep command is unnecessary surface area (Principle V, YAGNI).
- **Alternatives considered**: A `prune-staging` CLI — deferred; can be added later if an orphan
  source outside the three covered paths is found.

## Existing-code facts relied upon

- `_merge_and_write` builds one SQL string and calls `execute_sql` once (atomic batch). It is called
  per attachment (representative + each sibling) inside `apply_extractions`. Appending the staging
  DELETE there covers every applied attachment exactly once.
- Siblings of a shared-NF group have NO staging rows of their own (only the representative's pages
  are classified). A sibling's `_merge_and_write` would issue a DELETE that matches zero rows — a
  harmless no-op — so per-attachment cleanup is correct for groups.
- `mark_pending` accepts `attachment_ids` and/or `entry_ids`, builds OR-joined WHERE clauses, and
  returns 0 (no-op) when neither is given — FR-004 is preserved by guarding the prune behind the
  same "any ids?" check.
- `page_classifications` is analysis-owned; deleting from it does not touch the mirror tables
  (FR-005).
