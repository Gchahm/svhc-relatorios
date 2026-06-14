# Data Model: Data-correction audit trail + reversibility

**Feature**: 054-correction-audit-trail | **Date**: 2026-06-13

## New table: `data_corrections` (analysis-owned)

One row per **changed field** of one apply-correction call. Analysis-owned (like `attachment_state`,
`page_classifications`, `alerts`); never written by the scraper, never a mirror table. Drizzle
definition in `src/db/fiscal.schema.ts`; created by migration `drizzle/0014_*.sql`.

| Column | Type (SQLite / Drizzle) | Null | Notes |
|--------|--------------------------|------|-------|
| `id` | text (uuid) PK | no | `det_id("data_correction", batch_id, page_label, field)` — per-field, idempotent |
| `batch_id` | text | no | `det_id("data_correction_batch", attachment_id, target_finding_key, canonical(corrected_pages))` — correlates the rows from one apply-correction call (list/undo together) |
| `attachment_id` | text | no | the corrected attachment (`attachments.id`); FK reference (no ON DELETE action, like the other analysis tables) |
| `period` | text (len 7) | yes | `YYYY-MM` of the attachment's entry — for scoped listing; derived at record time |
| `page_label` | text (len 20) | no | the corrected page (e.g. `p1`), matching the staging key |
| `field` | text | no | the corrected frozen field name (e.g. `valor_total`, `cnpj_emitente`) |
| `from_value` | text | yes | the previous value as JSON-encoded text (null if the field was absent/null) |
| `to_value` | text | yes | the corrected value as JSON-encoded text |
| `evidence` | text | yes | the page image `read_path` (or page ref) the decision was based on (FR-013) |
| `agent` | text | no | acting agent/actor id (e.g. `triage-agent`, or a human username on undo); defaults to a non-empty sentinel |
| `target_finding_key` | text | yes | the finding the correction targeted (the `mismatch_key` it was meant to clear) |
| `status` | text (len 20) | no | `applied` \| `rolled-back` \| `flagged` \| `reverted` |
| `detail` | text | yes | free-text outcome/reason (verify-after result, rollback reason, undo note) |
| `from_staging` | text | yes | JSON snapshot of the attachment's pre-correction `page_classifications` rows — the restore input for rollback/undo |
| `created_at` | integer (timestamp_ms) | no | apply time |
| `reverted_at` | integer (timestamp_ms) | yes | set when status → `reverted` (undo) |
| `reverted_by` | text | yes | actor that performed the undo |

Indexes: `data_corrections_attachment_id_idx` on `attachment_id`, `data_corrections_status_idx` on
`status`, `data_corrections_period_idx` on `period` (mirrors the alerts/page_classifications index
style — supports the FR-006 scoped listing).

### Notes on storage shape
- `from_value`/`to_value` are JSON-encoded so a number, string, or null round-trips unambiguously
  (the frozen fields are number-or-null / string-or-null). The human-facing diff is `field: from→to`.
- `from_staging` carries the FULL attachment staging snapshot once per `batch_id` (it is identical
  across the per-field rows of a batch; stored on each row for query simplicity and so a single row
  is self-contained for undo). It is the deterministic restore input (research D3).
- The table is independent of the code-fix `<period>.verdicts.json` store (US3-AC2) — different
  storage (D1 vs cache), different schema, different semantics.

## Status lifecycle (research D7)

```
apply-correction (data changes):
    verify-after PASS                         → applied
    verify-after FAIL, restore OK             → rolled-back
    verify-after FAIL, restore ALSO FAILS     → flagged   (human-needed; data left as-is, surfaced)
apply-correction (no field changed)           → (no row written; "nothing to correct", FR-009)
apply-correction (target finding not in BEFORE)→ (no row written; unverifiable, fail-closed, FR-010)

undo-correction:
    on status == applied, restore OK          → reverted (sets reverted_at, reverted_by)
    on status in {rolled-back, flagged, reverted} → rejected, no change (FR-008)
```

`rolled-back` and `flagged` records still persist with their `from`/`to`/evidence so a human sees
that an attempt was made and what its outcome was.

## Entities (spec → model mapping)

- **Data correction** (spec) → one `data_corrections` row per changed field, grouped by `batch_id`.
- **Correction batch / apply request** (spec, transient) → the inputs to `apply_correction(...)`;
  not a stored table, but its identity is the `batch_id` stamped on each produced row.

## Reused (read-only or via existing writeback) tables — no change

- `page_classifications` (staging — read for snapshot/diff, written via `record_classification` +
  the restore batch; existing behavior).
- `attachment_analyses` / `attachment_analysis_records` / `attachment_state` (re-derived by the
  existing `apply_extractions` / `_merge_and_write`).
- `documents` / `document_entries` / `alerts` (refreshed by the existing `build_documents` /
  `run_analysis`).
- `attachments` / `entries` / `accountability_reports` (MIRROR — read-only here; never written).

## Migration

`drizzle/0014_<name>.sql` (generated by `pnpm db:generate`): `CREATE TABLE data_corrections (...)` +
the three indexes. No data backfill (new, initially empty). Local: `pnpm db:migrate:dev`.
