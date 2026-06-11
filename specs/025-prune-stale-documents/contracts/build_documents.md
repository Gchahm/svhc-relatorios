# Contract: `build_documents` (authoritative write)

Internal Python contract (no HTTP endpoint — the documents builder is a CLI/pipeline function).

## Signature (unchanged)

```python
def build_documents(target: Target = "local") -> tuple[int, int]:
    """Returns (documents_upserted, links_upserted)."""
```

The return type is preserved for backward compatibility (`run_analysis` and the `build-documents` CLI
ignore the return value today; pruned counts are surfaced via the log, not the return).

## Behavioral contract

Given the current `attachment_analyses` (read globally), after the call the persisted `documents` and
`document_entries` rows MUST equal **exactly** the desired sets the analyses produce:

- **C1 (upsert)**: every desired document and link is present (`INSERT OR REPLACE`).
- **C2 (prune links)**: no `document_entries` row whose id is absent from the desired link set remains.
- **C3 (prune documents)**: no `documents` row whose id is absent from the desired document set remains.
- **C4 (empty state)**: if no analysis carries a confident `(number, CNPJ)` key, ALL documents and ALL
  links are removed.
- **C5 (atomic)**: the prune DELETEs and the upsert INSERTs are submitted in ONE `d1.execute_sql` call
  (one wrangler invocation / one D1 implicit transaction). A failure does not commit the prune without
  the upsert (or vice versa).
- **C6 (no-op)**: when there is nothing to prune and nothing to upsert, no `execute_sql` is issued.
- **C7 (log)**: the run log reports upserted document/link counts AND pruned document/link counts.
- **C8 (global)**: the prune covers all periods; it is independent of any period filter on the
  surrounding analysis run.

## SQL shape

```sql
-- one batch:
DELETE FROM document_entries WHERE id NOT IN ('l1','l2',...);   -- or DELETE FROM document_entries; when desired links empty
DELETE FROM documents        WHERE id NOT IN ('d1','d2',...);   -- or DELETE FROM documents;        when desired docs empty
PRAGMA defer_foreign_keys = ON;
-- documents ( ... ) INSERT OR REPLACE ...
-- document_entries ( ... ) INSERT OR REPLACE ...
```

(The PRAGMA + INSERTs come from `d1.upsert_sql({...})`; the DELETEs are prepended by the caller.)

## Test contract (unit, stdlib `unittest` — `scripts/tests/test_document_prune.py`)

- **T1**: changed key — analyses produce only D2/L2; the emitted batch deletes everything but D2/L2 and
  inserts D2/L2 in one `execute_sql` call. (C1, C2, C3, C5)
- **T2**: empty desired state — no confident analyses; the batch is an unconditional
  `DELETE FROM document_entries; DELETE FROM documents;` with no INSERT, in one call. (C4)
- **T3**: prune uses `NOT IN (<desired ids>)` (non-empty) — the desired ids appear in the DELETE
  predicate, not the stale ids.
- **T4**: idempotent / no-op — when there is nothing persisted to prune and no rows to upsert, no
  `execute_sql` is issued. (C6)
- **T5**: pruned counts logged — given a pre-read returning ids not in the desired set, the log reports
  a non-zero pruned count. (C7)
