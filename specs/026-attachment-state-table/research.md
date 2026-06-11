# Phase 0 Research: Analysis-owned attachment state table

All Technical Context items were resolvable from the existing codebase and the issue;
no external research was required. The decisions below record where in the code each
write lives today and how it moves.

## Decision 1: State location — new `attachment_state` table keyed by `attachment_id`

- **Decision**: Create `attachment_state(attachment_id TEXT PRIMARY KEY REFERENCES attachments(id), classified_at INTEGER)`.
  Hold ONLY the classification timestamp. The absence of a row (or a row with NULL
  `classified_at`) means "pending".
- **Rationale**: 1:1 with `attachments`, matches the issue's suggested shape, and is the
  minimal surface that satisfies the invariant. Keeping it a separate row means the scraper's
  `INSERT OR REPLACE` on `attachments` cannot touch analysis state (fixes the BUG-001 race).
- **Alternatives considered**:
  - *Reuse `attachment_analyses` as the pending marker* (an attachment with an analysis row is
    "classified"). Rejected: error rows / partial writes muddy "classified", and the existing
    code stamps even error rows; a dedicated timestamp is clearer and preserves the current
    "attempted = classified" semantics.
  - *Move `content_hash` into the state table too.* Rejected — `content_hash` is derived from
    scraped page bytes and is written by the scraper at scrape time, so it is legitimately
    scraper-owned. Moving it would add churn and split a scraper-owned value across two tables.
    (Spec Assumptions; issue calls this "borderline".)

## Decision 2: Pending-set read — LEFT JOIN in the loader, not in `select_work`

- **Decision**: The loader's attachment query (`SELECT d.* FROM attachments d JOIN entries …`)
  becomes `SELECT d.*, s.classified_at AS classified_at FROM attachments d JOIN entries e …
  LEFT JOIN attachment_state s ON s.attachment_id = d.id`. `select_work` keeps reading
  `doc.get("classified_at")` unchanged.
- **Rationale**: `select_work` (and the loop-state / mismatch readers) already consume
  `classified_at` off the attachment dict. Joining it back in at the loader keeps every
  downstream consumer untouched — the smallest possible diff. After the column is dropped from
  `attachments`, `d.*` no longer carries it, so the explicit JOIN-aliased column supplies it.
- **Alternatives considered**: Query `attachment_state` separately in `select_work`. Rejected —
  duplicates the join logic and bypasses the loader, which is the single attachment-loading seam.

## Decision 3: Classified stamp — atomic, into `attachment_state`

- **Decision**: In `attachments.py:_merge_and_write`, replace
  `UPDATE attachments SET classified_at = <now> WHERE id = '<id>'` with an upsert into
  `attachment_state` in the SAME `execute_sql` batch:
  `INSERT INTO attachment_state(attachment_id, classified_at) VALUES('<id>', <now>)
   ON CONFLICT(attachment_id) DO UPDATE SET classified_at = excluded.classified_at;`
- **Rationale**: Feature 024's atomicity guarantee (FR-004) is preserved verbatim — the two
  DELETEs, the `attachment_analyses` INSERT, and the state upsert remain one D1 implicit
  transaction, so a failed insert leaves the attachment pending (no state row written / left
  NULL). Only the *target table* of the final statement changes.
- **Alternatives considered**: `INSERT OR REPLACE INTO attachment_state` — equivalent here
  (single column besides PK) but `ON CONFLICT … DO UPDATE` is explicit about intent and matches
  D1/SQLite idiom; either is acceptable.

## Decision 4: `mark-pending` — write `attachment_state`, never `attachments`

- **Decision**: In `extractions.py:mark_pending`, replace
  `UPDATE attachments SET classified_at = NULL WHERE <where>` with a clear of the state rows for
  the same id set. Setting `classified_at = NULL` (rather than deleting the row) keeps the row's
  existence harmless and matches "NULL = pending". Implementation:
  `UPDATE attachment_state SET classified_at = NULL WHERE attachment_id IN (<ids>)` — the id set
  is derived the same way it is today (the `<where>` already resolves to attachment ids, possibly
  via entry ids; see existing `mark_pending`). When the `<where>` selects by entry id, resolve to
  `attachment_id` via `attachments` (read-only) first, or join in the UPDATE.
- **Rationale**: Re-queue must not touch the mirror table (FR-005). A row that has no state yet is
  already pending, so clearing only existing rows is sufficient; no row needs to be created to
  mark something pending.
- **Alternatives considered**: `DELETE FROM attachment_state WHERE …`. Equivalent observable
  effect (no row ⇒ pending). UPDATE-to-NULL chosen to keep a stable row for a future audit trail
  and to mirror the old column-clear semantics most closely.

## Decision 5: Remove the analysis-side `content_hash` backfill

- **Decision**: Delete `_backfill_content_hashes` and its call in `scripts/analysis/images.py`,
  and drop the `attachments_needing_hash_backfill` guard's write path. Keep computing the hash
  **in memory** for the current run's grouping (the existing `doc["content_hash"] = h` assignment
  on the in-memory dict stays — it is not a D1 write).
- **Rationale**: This is the last analysis-side write to `attachments` (FR-002/FR-006/FR-007).
  Grouping continues to work via the in-memory fallback in `nf_groups.group_attachments`
  (`content_hash` falls back to a compute-from-cache). The scraper's `run_download_docs` already
  writes `content_hash` for rows it (re)downloads, so the backfill responsibility is the
  scraper's (FR-007). A row that has `file_path` but a NULL `content_hash` (scraped pre-016, never
  re-downloaded) is covered for grouping by the in-memory hash for that run — an accepted
  tradeoff documented in the spec; persisting it would re-introduce the violation.
- **Alternatives considered**: Extend the scraper to also re-hash `file_path`-present /
  `content_hash`-NULL rows. Rejected for this feature's scope — it's a separate scraper
  enhancement; the in-memory fallback already keeps grouping correct, so it is not required to
  fix the invariant. Noted as a follow-up in quickstart.

## Decision 6: Migration — copy `classified_at`, drop the column

- **Decision**: Drizzle schema: add `attachmentState`, remove `classifiedAt` from `attachments`.
  Generate the migration via `pnpm db:generate` (drizzle-kit). Because drizzle-kit's generated
  SQL won't know to copy data before dropping, hand-augment the generated migration with the
  data-copy step BEFORE the column drop, in this order:
  1. `CREATE TABLE attachment_state (...)`
  2. `INSERT INTO attachment_state (attachment_id, classified_at) SELECT id, classified_at FROM attachments WHERE classified_at IS NOT NULL;`
  3. drop `attachments.classified_at` (SQLite table-rebuild as drizzle-kit emits).
- **Rationale**: SC-003 (no spurious re-classification) requires carrying existing timestamps
  over before the column disappears. The constitution allows editing the generated migration's
  body for a data step as long as the schema change itself flows through `db:generate` (the
  *schema* is the source of truth; the migration is its committed artifact). The data-copy is
  pure SQL within the same migration file.
- **Alternatives considered**: A separate data-only migration. Rejected — splitting create/copy/
  drop across files risks an intermediate state where the column is dropped before the copy ran;
  one migration keeps it atomic per SQLite's transactional DDL.
- **Note on tooling**: `pnpm db:generate` is run via `node_modules/.bin/drizzle-kit` directly if
  the `pnpm <script>` shim fails in the sandbox (known workaround). The generated file is then
  hand-augmented with step 2 and reviewed.
