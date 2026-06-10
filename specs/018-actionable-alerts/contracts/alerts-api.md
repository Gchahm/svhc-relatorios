# Contract: `GET /api/alerts`

Auth: unchanged (role in `["admin","member"]`, else 403).

## Change

Add `metadata` to the selected columns. Ordering unchanged
(`asc(resolved), desc(severity), desc(referencePeriod)`).

## Response (each row)

```jsonc
{
  "id": "string",
  "type": "string",
  "severity": "critical | warning | info",
  "title": "string",
  "description": "string",
  "referencePeriod": "YYYY-MM",
  "resolved": false,
  "resolvedAt": null,
  "notes": null,
  "metadata": "string | null"   // NEW — raw JSON text from alerts.metadata, parsed client-side
}
```

- `metadata` is returned **verbatim** as stored (JSON string or null). The client parses it
  defensively; malformed/absent metadata → no links (never throws).
- No new query parameters. No pagination change.

## Notes

- `alerts.metadata` already exists in the schema — no migration.
- Metadata may contain `entry_ids` (array), `entry_id` (string), `attachment_ids` (array),
  `attachment_id`, `kind`, `ledger_value`, `extracted_value`, plus check-specific fields.
  The client only relies on the entry keys to build links (see deep-link.md).
