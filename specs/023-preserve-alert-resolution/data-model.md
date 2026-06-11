# Data Model: Preserve user-set alert resolution state across analysis re-runs

No schema change. This documents the existing `alerts` row and the ownership boundary the fix
enforces.

## Entity: Alert (`alerts` table)

| Column             | Type (D1/SQLite)        | Owner     | Notes |
|--------------------|-------------------------|-----------|-------|
| `id`               | text (uuid-shaped)      | pipeline  | **Deterministic**: `det_id("alert", period, type, discriminator)`. Stable across re-runs — the join key for preservation. |
| `created_at`       | integer (ms)            | pipeline  | Stamped at write (`now_ms()`). |
| `type`             | text(50)                | pipeline  | e.g. `attachment_amount_mismatch`, `document_overpayment`. |
| `severity`         | text(20)                | pipeline  | critical / warning / info. |
| `title`            | text(200)               | pipeline  | Volatile copy — NOT used for matching. |
| `description`      | text                    | pipeline  | Volatile copy — NOT used for matching. |
| `reference_period` | text(7) `YYYY-MM`       | pipeline  | Per-period writeback scopes its delete on this. |
| `metadata`         | text (JSON) nullable    | pipeline  | Drives deep links (feature 018). |
| **`resolved`**     | integer (0/1) notnull   | **user**  | Set via PATCH `/api/alerts/[id]`. **Preserved** on re-run. |
| **`resolved_at`**  | integer (ms) nullable   | **user**  | Set when resolved. **Preserved** on re-run. |
| **`notes`**        | text nullable           | **user**  | Free text. **Preserved** on re-run. |

### Ownership boundary (the crux of the fix)

- **Pipeline-owned** columns are recomputed every run and overwrite freely.
- **User-owned** columns (`resolved`, `resolved_at`, `notes`) MUST survive a re-run when the
  alert is re-emitted with the same `id`.

### State transitions

```
(no row)  --finding detected-->  row written: resolved=0, resolved_at=NULL, notes=NULL   [FR-005]
row (resolved=0) --user PATCH resolve--> resolved=1, resolved_at=<ms>, notes=<text>
row (resolved=1) --pipeline re-run, finding re-fires--> SAME id re-inserted, resolution GRAFTED back  [FR-001/002]
row (resolved=1) --pipeline re-run, finding no longer fires--> id absent from new set => row DELETED  [FR-003]
(no row) --finding re-appears after a gap--> fresh row, resolved=0 (no prior row to graft)  [edge case]
```

## Derived structure: preservation map

Transient, in-memory only (not persisted):

```
existing: { id -> { "resolved": int, "resolved_at": int|None, "notes": str|None } }
```

Built from `SELECT id, resolved, resolved_at, notes FROM alerts WHERE <delete-scope>`, keeping
only entries where `resolved` is truthy OR `notes` is non-empty. Applied by overwriting those
three keys on the freshly-built insert rows whose `id` is present in the map.

## Scopes

| Writeback        | Delete scope (existing)                          | Preservation read scope (same) |
|------------------|--------------------------------------------------|--------------------------------|
| Per-period       | `WHERE reference_period = '<p>'`                 | same WHERE                     |
| document_overpayment (global) | `WHERE type = 'document_overpayment'` | same WHERE                     |
