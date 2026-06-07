# Contract: Work manifest `<period>.extract-todo.json`

Produced by `docs-plan`; consumed by the `analyze-docs` agent and by `apply-extractions`.

## Shape

```jsonc
{
    "period": "string YYYY-MM",
    "data_dir": "string (the --data-dir used)",
    "generated_for": {
        "min_amount": "number | null",
        "limit": "number | null",
        "reanalyze": "boolean",
        "document_ids": "string[] | null",
        "entry_ids": "string[] | null",
    },
    "groups": [
        {
            "group_key": "string",
            "representative_document_id": "string (uuid)",
            "group_size": "integer >= 1",
            "sibling_sum": "number (sum of member entry amounts over the FULL group)",
            "pages": [
                {
                    "page_index": "integer >= 0",
                    "page_label": "string (e.g. p1)",
                    "path": "string (original file_path token, relative-to-scripts; extraction key)",
                    "read_path": "string (absolute path for the agent's Read tool)",
                },
            ],
            "members": [
                {
                    "document_id": "string (uuid)",
                    "entry_id": "string (uuid)",
                    "entry_amount": "number",
                    "vendor_name": "string | null",
                    "is_representative": "boolean",
                },
            ],
        },
    ],
}
```

## Invariants

- Exactly one member per group has `is_representative: true`; its `document_id` ==
  `representative_document_id`.
- `pages` lists the representative document's page images, in `page_index` order.
- `group_size` == number of `members`; `sibling_sum` sums every member's `entry_amount` (full group,
  pre-filter), matching the current reconciliation total.
- Groups are emitted only for documents selected by `select_work` (filters + skip-already-analyzed,
  unless `reanalyze`/targeted ids). An empty `groups` array means nothing to analyze.
- `path` is byte-for-byte the string used as the extractions-file key, so matching is exact.

## Producer obligations (`docs-plan`)

- Reuse `select_work` (the factored-out selection) and `group_documents` so the manifest reflects
  the same documents the old `run_document_analysis` would have analyzed under the same flags.
- Resolve `read_path` to an absolute path from the original `path` at plan time.
- Resolve `vendor_name` via the period refs at plan time (so `apply` needs no refs).
