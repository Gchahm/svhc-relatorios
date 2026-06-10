# Data Model: Real Documents Entity

## New table: `documents` (Drizzle `documents`, SQL `documents`)

One row per unique fiscal document. **Global** (not period-scoped).

| Field | Type | Notes |
|-------|------|-------|
| `id` | text PK | `crypto.randomUUID()` default in Drizzle; the Python build writes `det_id("document", normalized_number, issuer_cnpj)` so the id is a pure function of the key (idempotent upsert). |
| `document_number` | text(100), not null | **Normalized** NF/document number (trimmed, separators stripped, uppercased). The key part, also displayed. |
| `issuer_cnpj` | text(14), not null | Issuer CNPJ, digits only (exactly 14). The other key part. |
| `issuer_name` | text(200) | Display name from the analysis (`attachment_analyses.issuer_name`). Nullable. |
| `document_type` | text(50) | NF / NFS-e / receipt / boleto / … from `attachment_analyses.document_type`. Nullable. |
| `total_value` | real | Invoice gross — **max** confident `nf_total_for_reconciliation` across the document's analyses. Nullable (no confident total ⇒ "unknown" status, no overpayment). |
| `created_at` / `updated_at` | integer (timestamp_ms) | `timestamps` helper. |

**Indexes**:
- `uniqueIndex documents_number_cnpj_idx (document_number, issuer_cnpj)` — the dedup key (FR-001).
- `index documents_type_idx (document_type)` — list filter by type.

**Validation / derivation rules**:
- Created only when normalized number is non-empty AND CNPJ reduces to exactly 14 digits (FR-004).
- `total_value` recomputed each global build run (deterministic max) — never read-modify-write.

## New table: `document_entries` (join, Drizzle `documentEntries`, SQL `document_entries`)

The N:N link between a document and a ledger entry it is referenced by.

| Field | Type | Notes |
|-------|------|-------|
| `id` | text PK | Python writes `det_id("document_entry", document_id, entry_id)` (idempotent). |
| `document_id` | text, not null, FK → `documents.id` | |
| `entry_id` | text, not null, FK → `entries.id` | |
| `source_attachment_id` | text, FK → `attachments.id` | Provenance — the attachment whose analysis evidenced the link. Amount is NOT stored (read live). |
| `created_at` | integer (timestamp_ms) | |

**Indexes**:
- `uniqueIndex document_entries_doc_entry_idx (document_id, entry_id)` — at most one link per pair (FR-002).
- `index document_entries_document_id_idx (document_id)`.
- `index document_entries_entry_id_idx (entry_id)`.

**Rules**:
- One link per (document, entry); links accrue across periods on re-runs (FR-006).
- Claimed/linked amount = live `entries.amount` (FR-013), never frozen here.

## Relations (Drizzle)

- `documents` → many `document_entries`.
- `document_entries` → one `documents`, one `entries`, one `attachments` (source).
- `entries` gains `documentEntries: many(documentEntries)` (optional, for symmetry — only add if used).

## Derived/computed (not stored)

| Name | How |
|------|-----|
| `linked_count` | `count(document_entries)` per document. |
| `sum_entries` | `sum(entries.amount)` over linked entries (live). |
| `status` | `reconcile_group(sum_entries, total_value)` → `over_claim` / `reconciled` / `under_claim` / `null`(unknown total). Listed as over/within/under/unknown badge. |
| overpayment | `status == "over_claim"` ⇒ `document_overpayment` alert. |

## Existing tables touched

- `alerts`: gains rows of `type='document_overpayment'` (no schema change — `metadata` JSON already exists). `duplicate_billing` no longer emitted.
- `scripts/common/d1.py` `TABLE_ORDER`: `documents` and `document_entries` inserted before `alerts` (FK order).

## Alert: `document_overpayment`

- `type` = `"document_overpayment"`, `severity` = `"critical"`.
- `reference_period` = max period among linked entries.
- `id` = `det_id("alert", reference_period, "document_overpayment", document_id)` (stable, idempotent).
- `metadata` = `{ document_id, document_number, issuer_cnpj, total_value, sum_entries, over_amount, entry_ids }` — `entry_ids` drives the feature-018 per-entry deep links.
