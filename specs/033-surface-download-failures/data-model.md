# Data Model: Surface partial attachment-download failures

No schema migration. No new table or column. This feature reads existing data and writes through
existing channels.

## Entities (existing — touched read/write)

### `attachments` (mirror table — READ ONLY here)

Relevant existing columns:

| Column | Type | Role in this feature |
|--------|------|----------------------|
| `id` | text (UUID) | Subject of the alert; component of the deterministic alert id. |
| `entry_id` | text (UUID) | Owning entry — alert metadata for the feature-018 deep link. |
| `external_document_id` | int | Portal doc id — alert metadata (provenance). |
| `file_path` | text, nullable | The "has stored pages" signal. **Falsy (NULL/empty) ⇒ missing pages ⇒ alert.** |

The scraper remains the only writer of this table. This feature reads `file_path` (scraper side, to
decide "failed this run"; analysis side, to decide "missing now").

### `scrape_runs` (WRITE via existing `errors` notes channel)

| Column | Type | Role in this feature |
|--------|------|----------------------|
| `status` | text(20) | Gains a third terminal value `partial` (alongside `running`/`success`/`error`). Precedence: fatal error → `error`; else any failed download → `partial`; else `success`. |
| `errors` | text, nullable | Free-form notes channel. Gains a per-affected-period line: `"N attachment(s) failed to download in <period>: <id>, <id>, …"`, joined with the existing fatal-error/consistency/parse notes by `\n`. |

No column added (a dedicated `failed_download_count`/`failed_download_ids` column is a deferred
follow-up; see research Decision 2).

### `alerts` (analysis-owned — WRITE via existing `run_analysis` per-period batch)

A new alert **type** flows through the unchanged table/columns:

| Field | Value |
|-------|-------|
| `id` | `det_id("alert", period, "attachment_not_downloaded", attachment_id)` — deterministic, idempotent. |
| `type` | `"attachment_not_downloaded"` |
| `severity` | `"warning"` |
| `reference_period` | the attachment's period |
| `title` | `"Comprovante não baixado em <period>"` |
| `description` | `"O lançamento referencia um comprovante do portal que não foi possível baixar (sem páginas armazenadas)."` |
| `metadata` (JSON) | `{attachment_id, entry_id, external_document_id}` |
| `resolved` / `resolved_at` / `notes` | default unresolved; user disposition grafted on re-fire by the existing feature-023 path in `run_analysis`. |

## State transitions

```
attachment downloaded (file_path present)  ──no alert──┐
                                                        │ download fails / never fetched
                                                        ▼
attachment missing pages (file_path NULL)  ──► alert `attachment_not_downloaded` emitted each run
                                                        │ operator runs download-docs backfill, pages fetched
                                                        ▼
attachment downloaded (file_path present)  ──► alert absent from recomputed set ⇒ deleted by the
                                                 per-period delete-then-insert (self-clears)
```

Run-status transition (within a single run's `finally`):

```
errors (fatal) present?  ── yes ──► status = "error"   (dominates)
        │ no
        ▼
any attachment failed download this run? ── yes ──► status = "partial"
        │ no
        ▼
status = "success"
```

## Derived/computed (pure, stdlib-only — `scripts/scraper/download_failures.py`)

- `failed_attachment_ids(attachments_out, attempted_ids) -> list[str]`: ids whose row is in the
  attempted set AND whose post-preserve `file_path` is falsy. Deterministic order (input order).
- `format_failure_note(period, failed_ids) -> str | None`: the run-note line, or `None` when empty.
- `resolve_status(has_fatal_errors, any_download_failed) -> str`: the precedence above.
