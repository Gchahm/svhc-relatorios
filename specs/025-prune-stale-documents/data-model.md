# Data Model: Prune stale documents and links after re-classification

No schema change. This feature changes only the **write semantics** of the documents builder; the two
affected tables keep their existing Drizzle definitions. Documented here for the prune logic's sake.

## Entities (existing, unchanged)

### `documents`

Pure derived data — rebuilt every `build_documents` run; no user-editable column.

| Column | Type | Notes |
|--------|------|-------|
| `id` | text (PK) | deterministic `det_id("document", number, cnpj)` |
| `document_number` | text(100) | normalized invoice number (identity component) |
| `issuer_cnpj` | text(14) | 14-digit CNPJ (identity component) |
| `issuer_name` | text(200) nullable | display only |
| `document_type` | text(50) nullable | display only |
| `total_value` | real nullable | max confident reconciliation total across the key's analyses |
| `created_at` | timestamp_ms | set on (re)insert |
| `updated_at` | timestamp_ms | set on (re)insert |

Unique semantic key: `(document_number, issuer_cnpj)`.

### `document_entries`

Pure derived data; N:N link between a document and a ledger entry.

| Column | Type | Notes |
|--------|------|-------|
| `id` | text (PK) | deterministic `det_id("document_entry", doc_id, entry_id)` |
| `document_id` | text (FK → documents.id) | |
| `entry_id` | text (FK → entries.id) | |
| `source_attachment_id` | text (FK → attachments.id) nullable | provenance |
| `created_at` | timestamp_ms | set on (re)insert |

Unique: `(document_id, entry_id)`.

## Derived-state lifecycle (the change)

`build_documents` computes, from the **current** `attachment_analyses` (global), two desired sets:

- **Desired document ids** = `{ det_id("document", number, cnpj) : analysis has confident (number,cnpj) }`
- **Desired link ids** = `{ det_id("document_entry", doc_id, entry_id) : same analyses }`

The persisted state MUST converge to exactly these sets each run:

1. **Insert/update** every desired document/link (`INSERT OR REPLACE`, as today).
2. **Prune** every persisted document/link whose id is NOT in the corresponding desired set:
   - `DELETE FROM document_entries WHERE id NOT IN (<desired link ids>)`
   - `DELETE FROM documents WHERE id NOT IN (<desired doc ids>)`
   - When a desired set is empty → unconditional `DELETE FROM <table>` (the empty state IS the
     correct authoritative state; `NOT IN ()` is invalid SQLite).
3. Steps 1 + 2 are submitted as **one atomic batch** (single `execute_sql`).

Ordering inside the batch: delete links → delete docs → insert (PRAGMA `defer_foreign_keys = ON` from
`build_sql` relaxes intra-batch FK ordering, but links-before-docs is the FK-safe natural order).

### State transitions

| Before | Analyses now produce | After |
|--------|----------------------|-------|
| Doc D1 + link L1 for entry E | D2 (+ L2) for E (key changed) | D1, L1 removed; D2, L2 present |
| Doc D + links L1,L2 (two entries) | only L1 still confident | L2 removed; D + L1 kept |
| Doc D + link L | nothing confident anywhere | all documents + links removed |
| Doc D + link L | identical D + L | D, L re-asserted unchanged (idempotent) |
