# Contracts: Surface partial attachment-download failures

No HTTP API change. The "contracts" here are the data shapes/behaviors other code (and tests) depend
on.

## C1 — Pure scraper helper: `scripts/scraper/download_failures.py`

Stdlib-only, importable without `playwright`.

```python
def failed_attachment_ids(
    attachments_out: list[dict],   # the period's attachment rows, AFTER preserve merge
    attempted_ids: set[str],       # attachment ids for which a download was attempted this run
) -> list[str]:
    """Return ids of attempted attachments still missing pages (falsy file_path), input order."""

def format_failure_note(period: str, failed_ids: list[str]) -> str | None:
    """One run-note line, or None when failed_ids is empty.
    Format: "N attachment(s) failed to download in <period>: <id>, <id>, ..."."""

def resolve_status(has_fatal_errors: bool, any_download_failed: bool) -> str:
    """'error' if has_fatal_errors else 'partial' if any_download_failed else 'success'."""
```

Guarantees:
- `failed_attachment_ids` counts an id only if it is in `attempted_ids` AND its row's `file_path` is
  falsy → a preserved-prior-pages attachment is NOT counted.
- `format_failure_note` returns `None` (not an empty string) for the empty case so callers can skip
  appending.
- `resolve_status` precedence: fatal error dominates partial dominates success.

## C2 — Run record after a scrape (`scrape_runs`)

- `status ∈ {"running","success","error","partial"}`; `partial` iff ≥1 attachment failed download
  and no fatal error.
- `errors`: when any attachment failed, contains one `format_failure_note(...)` line per affected
  period (joined with other notes by `\n`); `NULL` only when there are no notes at all.

## C3 — Analysis check: `check_attachment_not_downloaded(period: PeriodData) -> list[Alert]`

Wired into `run_advanced`. For each attachment in `period.attachments` with falsy `file_path`,
returns one `Alert`:

```json
{
  "id": "det_id('alert', <period>, 'attachment_not_downloaded', <attachment_id>)",
  "type": "attachment_not_downloaded",
  "severity": "warning",
  "reference_period": "<period>",
  "title": "Comprovante não baixado em <period>",
  "description": "O lançamento referencia um comprovante do portal que não foi possível baixar (sem páginas armazenadas).",
  "metadata": {"attachment_id": "<id>", "entry_id": "<id>", "external_document_id": <int|null>}
}
```

Guarantees:
- Idempotent: re-running yields the same id (no duplicate).
- Self-clearing: an attachment with non-falsy `file_path` produces no alert, so the existing
  per-period delete-then-insert in `run_analysis` removes a previously-emitted one.
- Deep-link compatible: `metadata.entry_id` is what the frontend `AlertsClient` reads
  (`affectedEntryIds = entry_ids ?? [entry_id]`).
