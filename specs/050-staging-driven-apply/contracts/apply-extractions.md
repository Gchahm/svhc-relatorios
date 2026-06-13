# Contract: `apply-extractions` group selection

This is a behavioural contract for the `apply_extractions` function / `apply-extractions` CLI command.
No HTTP/API surface; the "contract" is the command's observable effect on D1.

## Command

```
python -m analysis apply-extractions --periodo <YYYY-MM> [--remote]
```

(Unchanged signature — no new flags. Scope continues to come from D1 state, not id arguments.)

## Selection rule (the change)

For each shared-NF group in the per-period plan:

| Precondition | Behaviour |
|---|---|
| Group representative attachment id ∈ `page_classifications` (any row, incl. an `error` row) | Group is **processed**: representative roll-up built from staging + group reconciliation + sibling fan-out + atomic delete-then-insert write + `classified_at` stamp + staging prune (unchanged). |
| Group representative attachment id ∉ `page_classifications` | Group is **skipped**: no read of its image bytes for roll-up, no write, no delete, no stamp. Its existing `attachment_analyses`, `attachment_analysis_records`, and `attachment_state` rows are unchanged; the attachment stays pending. |

## Invariants

- **INV-1 (safety)**: A pending attachment with an existing analysis and no staging rows has that
  analysis + records byte-identical before and after an `apply-extractions` run, and remains pending.
- **INV-2 (scoping)**: Given staging recorded for exactly one group's representative, `apply-extractions`
  writes/updates exactly that group's analyses (representative + siblings) and touches no other attachment.
- **INV-3 (parity)**: For any group whose representative has staging, the produced rows are identical to
  the pre-change output (same roll-up / reconciliation / fan-out / write).
- **INV-4 (empty scope)**: When no group in scope has staging, the command exits 0 and writes nothing.
- **INV-5 (no new D1 read)**: The selection uses the already-loaded per-period `page_classifications`
  list; the command issues no additional D1 query for selection.

## Out of scope (unchanged)

- `docs-plan` / `plan_extractions` output, the loader pending query, `mark-pending`, `classify-period`,
  `improve-classification`, the `_merge_and_write` atomic batch, and the staging prune all keep their
  current behaviour.
