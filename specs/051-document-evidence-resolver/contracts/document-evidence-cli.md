# CLI Contract: `document-evidence`

Part of the analysis CLI: `python -m analysis document-evidence --id <document_id> [--remote] [--cache-dir DIR]`

## Purpose

Resolve a **document** id to its source **attachment** id(s) and print that document's existing
classification findings + page-image `read_path`s in one shot. Read-only. The triage agent's single
evidence entry point — no ad-hoc SQL.

## Arguments

| Flag | Required | Type | Default | Meaning |
|------|----------|------|---------|---------|
| `--id` | yes | string | — | The document id (as shown by the UI/alert). |
| `--remote` | no | flag | off (local) | Read the REMOTE (production) D1 instead of local. |
| `--cache-dir` | no | string | `../.cache/analysis` | Ephemeral local scratch for materialized images. |

## Behavior

1. Verify the document id exists in `documents`. If not → print an error to stderr, exit non-zero.
2. Resolve the distinct, non-NULL `source_attachment_id` set from `document_entries` where
   `document_id = --id`.
3. Call the existing `summarize_mismatches(target, attachment_ids=<resolved set>, cache_dir=...)`.
4. Print one JSON object to stdout (see below). Exit 0.

## Output (stdout, JSON)

```json
{
  "document_id": "757dedb0...",
  "attachment_ids": ["att-aaa", "att-bbb"],
  "findings": [
    {
      "period": "2025-12",
      "attachment_id": "att-aaa",
      "entry_id": "ent-1",
      "kind": "amount",
      "ledger_amount": 320.0,
      "extracted_amount": 800.0,
      "page_refs": [
        {"attachment_id": "att-aaa", "page_label": "p1", "read_path": "/abs/path/.cache/analysis/2025-12/ent-1_p1.png"}
      ]
    }
  ]
}
```

- `attachment_ids`: resolved distinct source attachment ids, sorted.
- `findings`: the exact rows `summarize_mismatches` returns (each carrying `page_refs`). Empty when
  the document has no source attachments or its attachments currently carry no mismatches.

## Errors

| Condition | stderr | exit |
|-----------|--------|------|
| `--id` references no `documents` row | `error: document not found: <id>` | non-zero (1) |

## Guarantees

- **Read-only**: issues only `SELECT`s + the image materialization the reused summary already
  performs; mutates no table.
- **No drift**: finding shape + `page_refs` are produced by the unchanged `summarize_mismatches`.
- **Scope-tight**: findings cover only the document's source attachments; no unrelated attachment's
  findings appear.
