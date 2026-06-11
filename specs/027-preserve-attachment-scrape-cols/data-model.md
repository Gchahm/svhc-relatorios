# Data Model: Preserve scraper-owned attachment columns across re-scrapes

No schema change. This feature only governs which **values** the scraper writes to existing columns.

## Entity: `attachments` (existing table — unchanged shape)

| Column                 | Owner   | Always produced by scrape? | Behavior on re-scrape (this feature)                          |
|------------------------|---------|----------------------------|---------------------------------------------------------------|
| `id`                   | scraper | yes (deterministic)        | written fresh (unchanged)                                     |
| `entry_id`             | scraper | yes                        | written fresh (unchanged)                                     |
| `external_document_id` | scraper | yes                        | written fresh (unchanged)                                     |
| `file_path`            | scraper | only on successful download| **preserve existing if fresh value is NULL/empty**; else write fresh |
| `content_hash`         | scraper | only on successful download| **preserve existing if fresh value is NULL**; else write fresh |

The `attachments` table stays an exact portal mirror plus its two scraper-owned linkage columns
(`file_path`, `content_hash`). No analysis-owned column is added (FR-008).

## Entity: `attachment_state` (existing table — out of scope, regression guard)

Analysis-owned (`attachment_id` PK, `classified_at`). The scraper never reads or writes it; this
feature does not touch it. SC-003 asserts it is unchanged after a re-scrape.

## Transient working data (in-memory, during a scrape)

- **Freshly-scraped attachment rows** (`attachments_out`): the list the scraper builds for the
  period, each row's `file_path`/`content_hash` NULL unless filled by an in-run download.
- **Existing-column map** (`existing_by_id: dict[str, {file_path, content_hash}]`): read from D1
  for the period being scraped — `SELECT id, file_path, content_hash FROM attachments` joined to the
  period (via `entries` → `accountability_reports.period`). Used only to fill NULLs in the fresh rows
  before upsert; not persisted anywhere new.

## Invariants

- INV-1: After merge, every attachment row's `file_path`/`content_hash` is either a fresh non-NULL
  value (download succeeded this run) or the prior persisted value (when fresh is NULL) or NULL
  (no prior and no fresh).
- INV-2: The merge never changes `id`, `entry_id`, or `external_document_id`.
- INV-3: The merge is decided independently per `id` (no cross-row coupling).
- INV-4: For a new `id` not in the existing map, the row passes through unchanged.
