# Phase 1 Data Model: Dedicated Alert Detail Page

**No database schema change.** Read-only over existing tables plus the existing resolve update. This
describes the view model the detail page consumes.

## Source tables (read)

- `alerts` — the subject: `id`, `type`, `severity`, `title`, `description`, `referencePeriod`,
  `createdAt`, `resolved`, `resolvedAt`, `notes`, `metadata` (JSON text). Written by the pipeline; the
  resolve/reopen update touches `resolved`/`resolvedAt`/`notes` only.
- `entries` + `accountability_reports` — only as deep-link targets (entry id + period); not joined by
  the alert API (entry ids come from `metadata`; the entries view resolves them).
- `documents` — only as a cross-link target by id (`metadata.document_id`).

## View model

### `GET /api/alerts/[id]` → AlertDetail

```text
AlertDetail {
  id: string
  type: string
  severity: "critical" | "warning" | "info"
  title: string
  description: string
  referencePeriod: string        // YYYY-MM
  createdAt: number              // epoch ms
  resolved: boolean
  resolvedAt: number | null      // epoch ms
  notes: string | null
  metadata: string | null        // JSON text, parsed client-side
}
```

### Derived (client-side, from `metadata`)

```text
affectedEntryIds(metadata): string[]
  // entry_ids[] (duplicate_entry, negative_credit, duplicate_billing, large_expense_no_attachment),
  // else [entry_id] (attachment_* mismatches, feature 018), else [].

referencedDocumentId(metadata): string | null
  // metadata.document_id (document_overpayment) → link to /dashboard/documents/<id>.

evidenceFields(metadata): { key: string; label: string; value: string }[]
  // all metadata keys EXCEPT entry_ids/entry_id (rendered as entry links) and document_id
  // (rendered as a document link). Known keys get friendly labels + formatting:
  //   currency: total_value, sum_entries, over_amount, total, vendor_total, vendor_total,
  //             ledger_value, extracted_value (when numeric)
  //   percent:  pct, rate_pct
  //   plain:    count, paying, delinquent, kind, vendor_name, document_number, issuer_cnpj, date,
  //             description, movement_type, …  (unknown keys → readable string / JSON)
```

## Mutation

`PATCH /api/alerts/[id]` (existing) — body `{ resolved: boolean, notes?: string | null }`:
- sets `resolved`, `resolvedAt = resolved ? now : null`, `notes`.
- returns the updated alert; **extended** to also include `metadata` (currently omitted) so the client
  keeps a complete object.

## States

- Alert not found → `GET` 404 → "alert not found" UI (FR-011).
- `metadata` null/malformed → no entry links, no evidence; core fields still render (edge cases).
- Resolve/reopen failure → inline error; displayed status not flipped (FR-012).
- Auth: role ∈ {admin, member} or 403 (FR-013).
