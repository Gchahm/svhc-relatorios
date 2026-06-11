# Contract: `_preserve_existing_attachment_cols`

Pure merge helper in `scripts/scraper/runner.py`. The only new public-ish seam; unit-tested.

## Signature

```python
def _preserve_existing_attachment_cols(
    attachments_out: list[dict],
    existing_by_id: dict[str, dict],
) -> None:
    """Fill NULL file_path/content_hash on freshly-scraped attachment rows from existing D1 values.

    Mutates ``attachments_out`` in place. For each row, for each of ("file_path", "content_hash"):
    if the row's value is falsy (None / empty) AND ``existing_by_id`` has a non-falsy value for that
    row's id, copy the existing value onto the row. A non-falsy fresh value (successful in-run
    download) is left untouched, so it overwrites the prior value on upsert.
    """
```

- `attachments_out`: the period's freshly-built attachment row dicts (each has `id`, `entry_id`,
  `external_document_id`, `file_path`, `content_hash`).
- `existing_by_id`: `{attachment_id: {"file_path": str|None, "content_hash": str|None}}` read from
  D1 for the period being (re-)scraped. Empty `{}` on a first scrape.

## Behavior (maps to FR / SC)

| Case | Fresh value | Existing value | Result | Req |
|------|-------------|----------------|--------|-----|
| Re-scrape, no download | NULL | non-NULL | existing preserved | FR-001/002, SC-001 |
| Re-scrape, download succeeded | non-NULL | (any) | fresh value wins | FR-003, SC-002 |
| Partial download | per-id NULL vs non-NULL | non-NULL | each id decided independently | FR-004 |
| First scrape, no download | NULL | absent | stays NULL | FR-007, SC-004 |
| First scrape, download succeeded | non-NULL | absent | stays fresh value | FR-007, SC-004 |
| New id on re-scrape | NULL | absent | stays NULL | edge case |
| Prior NULL, fresh NULL | NULL | NULL/absent | stays NULL | edge case |

- MUST NOT modify `id`, `entry_id`, `external_document_id` (FR-006).
- MUST NOT read or write `attachment_state` (FR-005).
- MUST decide each column independently (a row may preserve `content_hash` but accept a fresh
  `file_path`, or vice versa).

## Integration contract (caller: `_scrape_periodo`)

- Before the `upsert_tables(period_data, ...)` call, the scraper reads
  `existing_by_id` via `d1.query("SELECT d.id, d.file_path, d.content_hash FROM attachments d JOIN
  entries e ON d.entry_id = e.id JOIN accountability_reports r ON e.report_id = r.id WHERE r.period =
  '<periodo>'", target=target)` and calls `_preserve_existing_attachment_cols(attachments_out,
  existing_by_id)`.
- The read is scoped to the period being scraped (no full-table scan).
- The read failing/returning empty MUST NOT block a first scrape (empty map ⇒ no-op preservation).
