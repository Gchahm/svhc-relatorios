# Data Model: NF multi-entry reconciliation

**Feature**: 005-nf-multi-entry-reconciliation | **Date**: 2026-06-06

No persisted schema changes. This documents the in-memory structures the pipeline computes and how existing persisted fields are reinterpreted.

## New in-memory structure: `NFGroup`

Computed per period from the period's documents + entries; not persisted.

| Field                        | Type          | Meaning                                                                                  |
| ---------------------------- | ------------- | ---------------------------------------------------------------------------------------- |
| `group_key`                  | `str`         | Joined md5 of the document's page image files (the "same NF" identity).                  |
| `document_ids`               | `list[str]`   | Documents whose page bytes are identical.                                                |
| `entry_ids`                  | `list[str]`   | The entries those documents are attached to (the siblings).                              |
| `entry_amounts`              | `list[float]` | Amounts of the sibling entries.                                                          |
| `sum_entries`                | `float`       | `sum(entry_amounts)`.                                                                    |
| `representative_document_id` | `str`         | The one document actually sent to the VLM (the group's first); its result is fanned out. |

A group of size 1 is the common single-entry case and is handled exactly as today.

## Reconciliation outcome (derived, per group)

Given the shared NF gross total `nf_total` (gross `valor_total` of the analyzed invoice page, else roll-up `extracted_amount`, else `None`) and tolerance `tol` (relative `< 0.05` OR absolute `<= 0.05`):

| Condition                      | Outcome                         | Per-sibling `amount_match`   | `duplicate_billing` alert |
| ------------------------------ | ------------------------------- | ---------------------------- | ------------------------- | ----------------------- | ---- |
| group size == 1                | unchanged single-entry behavior | per-entry compare (as today) | n/a                       |
| `nf_total is None`             | non-reconcilable                | unchanged / `None`           | none                      |
| `                              | sum_entries − nf_total          | `within`tol`                 | **reconciled**            | `True` for all siblings | none |
| `sum_entries − nf_total > tol` | **over-claim**                  | `False` for all siblings     | **emit**                  |
| `nf_total − sum_entries > tol` | **under-claim**                 | `False` for all siblings     | none                      |

## Existing persisted fields (reinterpreted, not changed)

### `document_analyses` row (period JSON → D1 table, unchanged schema)

- `amount_match` (boolean): now reflects **group** reconciliation when the document is part of a multi-entry NF group; unchanged per-entry meaning for single-entry documents.
- `extracted_amount`, identity fields, `analysis_records`: for siblings these are **fanned out from the single VLM pass** on the representative document (same values across the group). `document_id` remains per-document.

### `alerts` row (period JSON → D1 table, unchanged schema)

New row produced by `check_duplicate_billing`:

- `type`: `"duplicate_billing"`
- `severity`: `"critical"`
- `title`: e.g. `"Nota fiscal cobrada acima do valor em {period}"`
- `description`: human-readable summary (NF total vs. sibling sum vs. over-claim difference).
- `reference_period`: `YYYY-MM`
- `metadata` (JSON string): `{ nf_total, sum_entries, over_claim, entry_ids, document_ids, numero_documento?, cnpj_emitente? }`
- `id`: `det_id("alert", period, "duplicate_billing", <group discriminator>)` — deterministic / idempotent across re-runs.

## Entities (spec → implementation mapping)

| Spec entity              | Implementation                                         |
| ------------------------ | ------------------------------------------------------ |
| Nota Fiscal (NF) group   | `NFGroup` (in-memory), keyed by content md5            |
| Accountability entry     | existing `entries[]` dict in the period JSON           |
| Document analysis result | existing `DocAnalysisResult` / `document_analyses` row |
| Duplicate-billing alert  | existing `Alert` / `alerts` row, new `type`            |
