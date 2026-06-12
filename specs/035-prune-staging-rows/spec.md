# Feature Specification: Prune consumed and stale `page_classifications` staging rows

**Feature Branch**: `035-prune-staging-rows`  
**Created**: 2026-06-12  
**Status**: Draft  
**Input**: User description: "Prune consumed and stale page_classifications staging rows: apply-extractions deletes an attachment's staging rows after its authoritative attachment_analyses insert lands, and mark-pending clears a re-queued attachment's staging rows so reclassification starts clean (IMP-005, issue #42)"

## Context

`page_classifications` is the staging table between the vision skill (the
`record-classification` CLI) and `apply-extractions`. Rows are keyed
`(attachment_id, page_label)` and written with `INSERT OR REPLACE`, so re-classifying the
same page replaces its row — but **nothing ever deletes a row**. As a result the table is a
permanent, ever-growing copy of every page extraction ever recorded, and worse, it can hold
**stale** rows: a page that no longer exists in an attachment's `file_path` after a
re-scrape, or pages of an attachment that was removed entirely (portal deletion, issue #35).
A stale staging row can be silently re-applied by a future `apply-extractions` run — a
subtle correctness wrinkle, not just hygiene.

This feature makes the staging table self-cleaning so it only ever holds rows that are still
relevant to a not-yet-finalized attachment.

## Clarifications

### Session 2026-06-12

Running unattended; no blocking ambiguities required operator input. The following decisions
were auto-resolved from the issue and project conventions and are recorded here:

- Q: Which cleanup approach (issue suggestions 1/2/3)? → A: Suggestion 1 (apply consumes rows) + suggestion 3 (mark-pending invalidates); suggestion 2 (prune-by-validity) is unnecessary once consumed rows are deleted.
- Q: Per-row or per-attachment deletion on apply? → A: Per-attachment (all of an attachment's staging rows once its analysis lands).
- Q: Add a standalone global orphan-sweep command? → A: No — out of scope; existing portal-deletion cascade plus the two hooks cover all sources.
- Q: How does apply's staging delete stay safe against a failed write? → A: Folded into the same atomic `_merge_and_write` batch (commits with the insert, never alone).

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Consumed staging rows are removed after apply (Priority: P1)

When an operator runs `apply-extractions` for a period, each attachment whose extraction is
successfully rolled up into the authoritative `attachment_analyses` should have its staging
rows removed — the staging rows have served their purpose (their content is now frozen into
the authoritative analysis). The staging table stops accumulating consumed rows.

**Why this priority**: This is the primary fix for the "grows unbounded" problem and removes
the largest source of accumulated rows (every page ever applied). It also closes the
re-apply-stale-row correctness wrinkle for the common path, since a consumed row is gone.

**Independent Test**: Record classifications for an attachment's pages, run
`apply-extractions`, and confirm the attachment's `page_classifications` rows are gone while
its `attachment_analyses` / `attachment_analysis_records` rows are present.

**Acceptance Scenarios**:

1. **Given** an attachment with recorded staging rows for all its pages, **When**
   `apply-extractions` runs and the authoritative `attachment_analyses` insert lands, **Then**
   that attachment's `page_classifications` rows are deleted.
2. **Given** a shared-NF group (one representative attachment + siblings), **When**
   `apply-extractions` runs, **Then** the representative's staging rows are deleted after its
   roll-up is written (siblings have no staging rows of their own — only the representative's
   pages are classified — so nothing extra is deleted).
3. **Given** the authoritative `attachment_analyses` write for an attachment fails, **When**
   `apply-extractions` processes that attachment, **Then** its staging rows are **not** deleted
   (the attachment stays pending and self-heals on a re-run — the cleanup must commit with the
   write, never before it).

---

### User Story 2 - Re-queuing an attachment clears its stale staging rows (Priority: P2)

When an operator re-queues an attachment for re-classification with `mark-pending`, that
attachment's existing staging rows should be cleared so the new classification starts from a
clean slate — no leftover rows from a prior page set (e.g. after a re-scrape changed which
pages the attachment has).

**Why this priority**: This closes the second source of stale rows (a changed page set on
re-queue) and guarantees the new classification can't be polluted by a prior run's rows. It
depends conceptually on the same staging-row delete primitive as Story 1 but is a distinct
operator action.

**Independent Test**: Record staging rows for an attachment, run `mark-pending` for that
attachment, and confirm its `page_classifications` rows are gone (and its
`attachment_state.classified_at` is cleared as before).

**Acceptance Scenarios**:

1. **Given** an attachment with recorded staging rows, **When** `mark-pending` is run for that
   attachment id, **Then** its `page_classifications` rows are deleted in addition to its
   `attachment_state.classified_at` being cleared.
2. **Given** `mark-pending` is run with an entry-id scope, **When** it resolves entry ids to
   attachment ids, **Then** the resolved attachments' staging rows are deleted too.
3. **Given** `mark-pending` is run with no ids, **When** it executes, **Then** nothing is
   deleted (no-op, as today).

---

### Edge Cases

- **Page-error rows**: An attachment may have a staging row recorded as `{"error": ...}`. When
  the attachment is applied (an error row still produces an analysis result — error or not),
  its staging rows are deleted along with any field rows. Cleanup is per-attachment, not
  per-row-success.
- **Attachment with no staging rows applied**: An attachment selected for apply that has no
  staging rows at all (every page missing) still produces an (error) analysis row; the delete
  of its (empty) staging set is a harmless no-op.
- **Orphaned rows from removed attachments**: Portal deletions (issue #35) already
  cascade-clean `page_classifications` for the deleted attachment in the scraper's
  reconciliation. This feature does not add a separate global orphan sweep — the two cleanup
  hooks (apply + mark-pending) plus the existing cascade cover the identified accumulation
  sources. (Documented as an explicit out-of-scope assumption.)
- **Re-apply of a stale row**: With consumed rows deleted at apply time, a future
  `apply-extractions` cannot re-apply a row that was already consumed. A stale row whose page
  no longer exists in the current `file_path` is not looked up by the new plan (the plan's page
  set drives lookups), and on the next re-queue+apply cycle it is cleared by `mark-pending` /
  consumed by apply.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: `apply-extractions` MUST delete an attachment's `page_classifications` rows after
  its authoritative `attachment_analyses` (+ `attachment_analysis_records`) write for that
  attachment succeeds.
- **FR-002**: The staging-row deletion MUST be atomic with the authoritative write for that
  attachment — a failed authoritative write MUST NOT delete the staging rows (so the attachment
  stays pending and self-heals), and a successful write MUST commit the staging-row deletion in
  the same transaction (the delete never lands without the write, nor the write without the
  delete).
- **FR-003**: `mark-pending` MUST delete the `page_classifications` rows of every attachment it
  re-queues (both attachment-id scope and entry-id scope, the latter resolved through the
  existing read-only `attachments` lookup), in addition to clearing
  `attachment_state.classified_at` as it does today.
- **FR-004**: `mark-pending` with no attachment/entry ids MUST remain a no-op (delete nothing,
  clear nothing) and return 0, as today.
- **FR-005**: The cleanup MUST NOT touch the mirror tables (`entries`, `attachments`,
  `accountability_reports`) — `page_classifications` and `attachment_state` are analysis-owned,
  so the mirror invariant (only the scraper writes the mirror) is preserved.
- **FR-006**: Deleting an attachment's staging rows MUST be scoped strictly to that attachment's
  id (`attachment_id = …` / `attachment_id IN (…)`); it MUST NOT affect another attachment's
  staging rows.
- **FR-007**: The deletion logic MUST be expressed as SQL that composes with the existing
  delete-then-insert batch idiom (a SQL-returning helper that callers prepend/append to their
  one `execute_sql` batch), consistent with the project's atomic-writeback convention.

### Key Entities *(include if feature involves data)*

- **`page_classifications` (staging row)**: One per `(attachment_id, page_label)` page
  extraction. Input to the apply roll-up; after this feature it is deleted once consumed (apply)
  or invalidated (re-queue), so the table holds only rows for not-yet-finalized attachments.
- **`attachment_analyses` / `attachment_analysis_records` (authoritative analysis)**: The
  frozen roll-up produced from staging rows; its successful write is the trigger for consuming
  the staging rows.
- **`attachment_state` (classification state)**: Holds `classified_at`; `mark-pending` clears it
  and (after this feature) also clears the attachment's staging rows.

## Assumptions

- **No separate global orphan sweep.** The two cleanup hooks (apply consumes, `mark-pending`
  invalidates) plus the scraper's existing portal-deletion cascade (issue #35, which already
  cascade-cleans `page_classifications`) cover all identified accumulation sources. A standalone
  "sweep all orphaned staging rows" command is out of scope (suggestion 1 in the issue is the
  chosen approach; suggestion 2's "prune by validity on apply" is unnecessary once consumed rows
  are deleted; suggestion 3's `mark-pending` hook is included).
- **Per-attachment, not per-row, cleanup on apply.** Once an attachment's authoritative analysis
  lands, ALL of its staging rows are obsolete (their content is frozen into the analysis), so the
  delete targets `attachment_id`, not individual consumed `page_label`s. This also removes any
  stale leftover page rows for that attachment as a side effect.
- **No schema/migration change.** The feature only adds DELETE statements against the existing
  `page_classifications` table; no new column, table, or migration.
- **Idempotent.** Re-running apply or `mark-pending` after the rows are already gone is a harmless
  no-op (DELETE of zero rows).

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: After `apply-extractions` finalizes a period, the `page_classifications` row count
  for every successfully-applied attachment is 0 (the table no longer accumulates consumed rows
  across runs).
- **SC-002**: After `mark-pending` re-queues an attachment, that attachment's
  `page_classifications` row count is 0, so a fresh classification starts with no leftover rows.
- **SC-003**: A simulated failed authoritative write during apply leaves the attachment's
  staging rows intact (count unchanged) and the attachment pending, demonstrating the cleanup is
  not committed without the write.
- **SC-004**: No write is issued to any mirror table (`entries`, `attachments`,
  `accountability_reports`) by either cleanup path, preserving the mirror invariant.
