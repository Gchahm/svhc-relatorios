# Contract: `build-documents` CLI

## Command

```
python -m analysis build-documents [--remote]
```

(run from `scripts/`, via `uv`, like the other analysis commands.)

- `--remote`: operate on production D1 (default: local Miniflare state).
- **No `--periodo`**: the build is intentionally **global** — documents dedup across all periods. A period filter would corrupt cross-period dedup/links.

## Behavior

1. Query all attachment analyses globally from D1:
   `SELECT da.*, d.id AS attachment_id, d.entry_id, e.amount AS entry_amount FROM attachment_analyses da JOIN attachments d ON da.attachment_id = d.id JOIN entries e ON d.entry_id = e.id` (plus the per-page `attachment_analysis_records` for `nf_total_for_reconciliation`).
2. For each analysis: derive `(number, cnpj)` via `normalize_number` / `normalize_cnpj`. Skip when either is not confident (no document, no link).
3. Group analyses by the normalized key. Per group build one `documents` row:
   - `id = det_id("document", number, cnpj)`, `document_number = number`, `issuer_cnpj = cnpj`.
   - `issuer_name` / `document_type` = first non-empty across the group's analyses.
   - `total_value` = max confident `nf_total_for_reconciliation(record_responses, fallback=extracted_amount)` across the group (None if none confident).
4. Per analysis in a group build one `document_entries` row: `id = det_id("document_entry", document_id, entry_id)`, `document_id`, `entry_id`, `source_attachment_id = attachment_id`.
5. Upsert via `d1.upsert_tables({"documents": [...], "document_entries": [...]})` (INSERT OR REPLACE; deterministic ids + unique indexes ⇒ idempotent, links accrue).

## Output

- Logs counts: documents upserted, links upserted, analyses skipped (missing number/CNPJ).
- Exit 0 on success; non-zero on a wrangler/D1 failure (propagated from `d1`).

## Idempotency / re-run

- Re-running with unchanged inputs writes byte-identical rows (same ids, same total via deterministic max) — document and link counts unchanged (SC-004).
- Running after analyzing a new period adds that period's links to existing documents (SC-002).

## Integration

- `run_analysis` calls `build_documents(target)` once at the start (before the per-period checks), so `python -m analysis analyze` (and the `analyze-docs` agent's apply→analyze→mismatches sequence) produces documents automatically.
- `check_document_overpayment(target)` runs after building and after the per-period alert writeback; its alerts are written via a global `DELETE FROM alerts WHERE type='document_overpayment'` + upsert.
