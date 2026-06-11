# Phase 1 Data Model: Reconcile Portal Deletions

No schema change. This documents the rows the feature reads, deletes, and writes — all in existing
tables.

## Inputs (read from D1, per period, after upsert)

| Source | Columns read | Purpose |
|--------|--------------|---------|
| `entries` (via `report_id = report(period)`) | `id, date, description, amount` | diff + frozen evidence |
| `attachments` (via join `entries → accountability_reports`) | `id, entry_id, external_document_id` | diff + cascade keys |
| `category_subtotals` (via `report_id`) | `id` | diff |
| `approvers` (via `report_id`) | `id` | diff |

The *scraped* id sets come from the in-memory `period_data` the scrape just built (the same dict
passed to `upsert_tables`): `entries[].id`, `attachments[].id`, `category_subtotals[].id`,
`approvers[].id`.

## Derived sets (pure function)

- `stale_entry_ids = existing_entry_ids − scraped_entry_ids`
- `stale_attachment_ids = (existing_attachment_ids − scraped_attachment_ids) ∪ {attachments whose
  entry_id ∈ stale_entry_ids}` — an attachment is stale if it's gone from the scrape OR its owning
  entry vanished.
- `stale_subtotal_ids = existing_subtotal_ids − scraped_subtotal_ids`
- `stale_approver_ids = existing_approver_ids − scraped_approver_ids`
- `anything_stale = any of the above is non-empty`

## Deletes (one atomic batch, only when `anything_stale`)

Ordered child→parent (under `PRAGMA defer_foreign_keys = ON`):

1. `attachment_analysis_records` — `attachment_analysis_id IN (SELECT id FROM attachment_analyses WHERE attachment_id IN SA)`
2. `attachment_analyses` — `attachment_id IN SA`
3. `attachment_state` — `attachment_id IN SA`
4. `page_classifications` — `attachment_id IN SA`
5. `document_entries` — `entry_id IN SE OR source_attachment_id IN SA`
6. `attachments` — `id IN SA`
7. `entries` — `id IN SE`
8. `category_subtotals` — `id IN stale_subtotal_ids`
9. `approvers` — `id IN stale_approver_ids`

(`SE` = stale_entry_ids, `SA` = stale_attachment_ids. A delete whose id set is empty is omitted.)

## Vanished-row alert (written in the same batch, only when `anything_stale`)

Always preceded by `DELETE FROM alerts WHERE type='portal_row_vanished' AND reference_period='<p>'`
so the per-period alert is replaced, never duplicated. When `anything_stale` is false, the DELETE is
**still** issued alone (to clear a stale prior alert) and no INSERT follows.

| Column | Value |
|--------|-------|
| `id` | `det_id("alert", period, "portal_row_vanished")` (stable per period) |
| `created_at` | `now_ms()` |
| `type` | `"portal_row_vanished"` |
| `severity` | `"critical"` |
| `title` | e.g. `"3 ledger row(s) vanished from portal — 2026-01"` |
| `description` | human summary: counts per table + that they were removed from the portal between scrapes |
| `reference_period` | the period (`YYYY-MM`) |
| `metadata` | JSON (below) |
| `resolved` | `0` |
| `resolved_at` | `NULL` |
| `notes` | `NULL` |

### `metadata` JSON shape

```json
{
  "entry_ids": ["<deleted entry id>", "..."],
  "deleted_entries": [
    { "id": "...", "date": "2026-01-15", "description": "...", "amount": 123.45 }
  ],
  "deleted_attachment_ids": ["..."],
  "deleted_subtotal_ids": ["..."],
  "deleted_approver_ids": ["..."],
  "counts": { "entries": 1, "attachments": 1, "category_subtotals": 0, "approvers": 0 }
}
```

`entry_ids` is the feature-018 deep-link convention (the alerts UI reads `metadata.entry_ids` to
render affected-entry links); it degrades gracefully because the entries are now gone (the dialog
simply shows no analysis for a missing entry). `deleted_entries` holds the frozen evidence so the
loss is auditable after the rows are deleted (FR-006).

## State transitions

- **No prior data → first scrape**: existing sets empty → no stale → no delete, no alert.
- **Re-scrape, row removed on portal**: stale non-empty → cascade delete + alert insert.
- **Re-scrape, identical rows**: stale empty → DELETE-only of any stale prior alert, no insert.
- **Re-scrape, previously-vanished rows re-appear on portal**: they upsert back as normal rows; the
  prior period alert is cleared by the always-issued DELETE (and only re-inserted if *other* rows
  vanished this run).
