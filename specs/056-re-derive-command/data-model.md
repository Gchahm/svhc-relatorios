# Phase 1 Data Model: Re-derive command

No new tables, columns, or migrations. Re-derive reads and writes existing tables only.

## Entities touched (all existing)

### Read (input)

- **`attachment_analysis_records`** — the durable per-page transcription store. Re-derive reads, per in-scope attachment (joined via `attachment_analyses`):
  - `page_label` (TEXT) — staging key part `(attachment_id, page_label)`.
  - `page_index` (INT, nullable).
  - `response` (TEXT JSON) — the verbatim per-page transcription: a **typed** transcription (carries `doc_type`/`schema_version`) or a **legacy flat** record (no `doc_type`). This is the re-derive input; never modified.
  - `parse_error` (TEXT, nullable) — when set, the page had no parseable response; reconstructed staging carries it as `error`.
  - `analysis_type` (TEXT) — re-derive considers only `'page_extraction'` records.
- **`attachment_analyses`** — used to identify which attachments are already classified (have a row) and to join to their records. Read-only as input; rewritten as output by the apply path.
- **`attachments` / `entries` / `accountability_reports`** — read-only (mirror tables) for grouping (`content_hash`), entry amounts, vendor names, period membership. Never written.

### Write (output) — all analysis-owned, all via the reused apply/analyze path

- **`page_classifications`** — re-derive writes reconstructed staging rows here (one per `(attachment_id, page_label)` with the stored `response`), then the apply path consumes + prunes them (feature 035). Transient working state; ends empty for the re-derived attachments after a successful apply.
- **`attachment_state`** — `classified_at` cleared (re-queue) for in-scope attachments, then re-stamped by `_merge_and_write` after the roll-up lands.
- **`attachment_analyses`** + **`attachment_analysis_records`** — rebuilt by `apply_extractions` → `_merge_and_write` (atomic delete + insert per attachment).
- **`documents`** + **`document_entries`** — rebuilt globally by `build_documents` (inside `run_analysis`).
- **`alerts`** — refreshed atomically per affected period by `run_analysis`.

## Reconstructed staging row (the bridge)

The pure transform `staging_rows_from_records(records)` maps each `page_extraction` record dict to a `page_classifications`-shaped row:

| staging field   | source                                            |
|-----------------|---------------------------------------------------|
| `id`            | `page_classification_id(attachment_id, page_label)` (deterministic) |
| `attachment_id` | the attachment's id                               |
| `page_label`    | record `page_label` (rows without one are skipped)|
| `page_index`    | record `page_index`                               |
| `response`      | record `response` decoded to a dict (or `None`)   |
| `error`         | record `parse_error`                              |
| `recorded_at`   | `now_ms()`                                         |

This is identical to `corrections._snapshot_staging`'s output shape (the two now share the helper).

## State transitions (per in-scope attachment)

```
[classified, stored records present]
   → reconstruct staging rows from records (write page_classifications)
   → clear attachment_state.classified_at        (re-queue; staging untouched)
   → apply_extractions (staging-driven)          (roll up the group via fixed mappers; re-stamp; prune staging)
   → [re-derived, classified again]

[classified, no parseable stored record]
   → no staging row produced → skipped by staging-driven apply → [unchanged]  (FR-008)
```

## Invariants preserved

- **Idempotent**: `attachment_analyses` is a pure function of the staged transcription + the mappers; unchanged mappers ⇒ identical roll-up (modulo timestamps). (FR-007)
- **No empty overwrite**: an attachment with no reconstructable staging is never visited by the apply. (FR-008)
- **Mirror invariant**: zero writes to `entries`/`attachments`/`accountability_reports`. (FR-010)
- **Atomic writebacks**: inherited from `_merge_and_write` and `run_analysis` (feature 024).
