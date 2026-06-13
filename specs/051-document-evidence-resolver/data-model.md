# Phase 1 Data Model: Document→attachment(s) evidence resolver

**No schema change. No migration.** All tables read-only.

## Entities (existing, read-only)

### documents (read for existence check)
- `id` (text, PK) — the document id handed to the resolver.
- Existence of a row with this id distinguishes "unknown document" (FR-005, error) from
  "document with no source attachments / no findings" (FR-006, empty result).

### document_entries (read for resolution)
- `document_id` (text, FK → documents.id) — the filter.
- `source_attachment_id` (text, nullable, FK → attachments.id) — the provenance link to the
  attachment that produced this document-entry association.
- **Resolution**: `DISTINCT source_attachment_id WHERE document_id = <id> AND source_attachment_id
  IS NOT NULL` → the source attachment id set.

### (transitively, via `summarize_mismatches`) attachment_analyses, attachment_analysis_records, attachments, entries, alerts
- All read-only, exactly as the existing `mismatches` command reads them. The resolver does not
  read these directly; it passes the resolved attachment ids to `summarize_mismatches`.

## Output shape

A JSON object printed to stdout:

```json
{
  "document_id": "<id>",
  "attachment_ids": ["<src-att-1>", "<src-att-2>"],
  "findings": [ /* the exact rows summarize_mismatches produces, each with page_refs */ ]
}
```

- `attachment_ids` — the resolved distinct source attachment id set (sorted for determinism).
- `findings` — the existing scoped mismatch summary for those attachment ids (per-finding shape +
  `page_refs[].read_path` unchanged from the `mismatches` command).
- Empty `attachment_ids` ⇒ empty `findings` (FR-006), still a successful (exit 0) result.

## Error model

- Unknown `document_id` (no `documents` row) ⇒ message to stderr + non-zero exit (FR-005). No JSON.
