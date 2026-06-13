# Data Model: Staging-driven apply-extractions

**No schema change, no migration.** This feature only changes which existing rows `apply-extractions`
*selects to process*; it adds no table, column, or index.

## Entities (read/written, all pre-existing)

### page_classifications (staging) — READ ONLY here

One row per `(attachment_id, page_label)` recorded by the vision skill via `record-classification`.

- Relevant field: `attachment_id` (the selection signal).
- **Presence** of any row for a group's `representative_attachment_id` selects that group for apply.
- Loaded per period by `load_all_periods` into `PeriodData.raw["page_classifications"]` (already used by
  `build_plan`'s `recorded` flag and `D1ExtractionProvider`).
- Pruned by the unchanged `_merge_and_write` after a successful roll-up (feature 035) — which is exactly
  why a re-run finds a pending-but-unstaged bystander and previously clobbered it.

### attachment_analyses / attachment_analysis_records — WRITTEN only for processed groups

The authoritative roll-up. Written (delete-then-insert, atomic) by the unchanged `_merge_and_write`
**only** for groups the new filter processes. A skipped group's existing rows are left untouched (FR-002).

### attachment_state — WRITTEN only for processed groups

`classified_at` is stamped in `_merge_and_write`'s atomic batch for processed groups only. A skipped
group stays pending (no row or `classified_at IS NULL`), so it self-heals on a later real classification.

## Derived selection set (in-memory, transient)

- **`staged_ids: set[str]`** — `{ row["attachment_id"] for row in periods[period].raw["page_classifications"] }`.
  Computed per period inside `apply_extractions`. A group is processed iff
  `group["representative_attachment_id"] in staged_ids`.

## Group structure (unchanged, from `build_plan`)

Each plan group already carries `representative_attachment_id`, `group_size`, `sibling_sum`, `pages`,
and `members` (with `is_representative`). The filter reads `representative_attachment_id`; everything
else about a processed group is unchanged.
