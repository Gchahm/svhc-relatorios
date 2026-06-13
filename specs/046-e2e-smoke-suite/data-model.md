# Phase 1 Data Model: Synthetic Seed Dataset

All rows are **synthetic** and live in period `2099-01`. Ids are derived with `det_id(...)` exactly as the pipeline derives them, so the seed is byte-identical to production output and idempotent (re-running yields the same ids → `INSERT OR REPLACE` overwrites, no duplicates). Built by the pure `scripts/e2e/synthetic.py` (returns the table→rows dict + the R2 image plan); written by `scripts/e2e/seed.py` via `d1.upsert_tables` (FK order is `TABLE_ORDER`) + `d1.put_object`.

Constants: `PERIOD = "2099-01"`, fake CNPJ `"11222333000181"`, issuer/vendor names prefixed `EXEMPLO`, source URLs `https://example.svhc.local/...`.

## Reference + anchor rows

| Table | Rows | Notes |
|-------|------|-------|
| `scrape_runs` | 1 | id `det_id("scrape_run", PERIOD)`; `status='success'`, `executed_at=now_ms()` |
| `accountability_reports` | 1 | id `det_id("report", PERIOD)`; `scrape_run_id` → the run; `period='2099-01'`; totals synthetic; `source_url` set |
| `categories` | 2 | one `D` (Despesas), one `C` (Receitas); names `EXEMPLO Despesas`/`EXEMPLO Receitas` |
| `subcategories` | 2 | one per category |
| `vendors` | 2 | `EXEMPLO Fornecedor A`, `EXEMPLO Fornecedor B` |
| `units` | 1 | block `A`, number `101`, code `101A` |
| `category_subtotals` | 2 | consistent with the entry sums (so a future consistency check would pass) |
| `approvers` | 1 | `EXEMPLO Síndico`, status `approved` |

## Entries (6) — id `det_id("entry", PERIOD, date, description, str(amount), subcategory_id, "1")`

| key | amount | movement | vendor | role in tests |
|-----|--------|----------|--------|---------------|
| E1 | 100.00 | D | A | shared-NF group with E2 (over-claim document) |
| E2 | 100.00 | D | A | shared-NF group with E1 |
| E3 | 250.00 | D | B | "within" document |
| E4 | 50.00 | D | B | pending attachment (for `_merge_and_write` integration test) |
| E5 | 75.00 | D | A | reconciliation-vanish target (deleted in the reconcile test) |
| E6 | 500.00 | C | — | a credit (receita), no attachment — exercises the entries list breadth |

## Attachments (5) — id `det_id("attachment", entry_id)`; one per entry E1..E5

- `entry_id` (unique), `external_document_id` (synthetic int), `file_path` = `2099-01/<entry_id>_p1.png` (single page; E1/E2 share `content_hash` to model a shared NF), `content_hash` synthetic.
- **R2 plan**: one fake PNG per attachment uploaded at the `objectKeyFromFilePath`-derived key (`2099-01/<entry_id>_p1.png`). The PNG is a tiny valid 1×1 image generated in `synthetic.py` (constant bytes — no real document).

## attachment_state (5) — `attachment_id` PK

- E1, E2, E3 attachments: `classified_at = now_ms()` (classified).
- E4 attachment: **no row** (pending) — the `_merge_and_write` test stamps it.
- E5 attachment: `classified_at = now_ms()` (classified; reconcile test cascades it away).

## attachment_analyses (3 seeded) + records — id `det_id("attachment_analysis", attachment_id)`

| attachment | document_number | issuer_cnpj | document_type | total_value/extracted | drives |
|------------|-----------------|-------------|---------------|----------------------|--------|
| E1 | `NF-1001` | `11222333000181` | NF | 150.00 | over-claim doc (E1+E2 amounts=200 > 150) |
| E2 | `NF-1001` | `11222333000181` | NF | 150.00 | same doc key as E1 (shared NF) |
| E3 | `NF-1002` | `44555666000199` | NF | 250.00 | within doc (E3 amount 250 == total) |

- Each analysis has one `attachment_analysis_records` row (`analysis_type='page_extraction'`, `page_label='p1'`, `response` = synthetic JSON).
- `amount_match` etc. set so the entries page dialog shows real flags; E1's analysis has a mismatch flag to back the seeded alert.

## page_classifications (1) — staging rows for the E4 (pending) attachment

- One row `attachment_id` = E4's attachment, `page_label='p1'`, `response` synthetic JSON, `recorded_at=now_ms()`. The `_merge_and_write` integration test asserts this row is **deleted** after the writeback (feature 035 staging consume). `mark-pending` test re-asserts deletion on its own scope.

## documents + document_entries

- **Seeded as empty** — the `build-documents` integration test *produces* them from the analyses (so it tests the real derivation), then re-runs to test pruning. For the **browser** smoke, the seed runs `build-documents` once after the analyses are written, so the documents page has data. Net: `seed.py` writes analyses, then invokes `build_documents("local")` so `documents`/`document_entries` exist for the UI (over-claim `NF-1001`, within `NF-1002`).

## alerts (≥2) — id `det_id("alert", type, discriminator)`

| type | severity | reference_period | metadata | drives |
|------|----------|------------------|----------|--------|
| `attachment_amount_mismatch` | warning | 2099-01 | `{attachment_id: E1.att, entry_id: E1, kind:"amount", ledger_value:100, extracted_value:150}` | single-entry deep link → entries page highlight + dialog auto-open |
| `document_overpayment` | critical | 2099-01 | `{document_id, document_number:"NF-1001", issuer_cnpj, total_value:150, sum_entries:200, over_amount:50, entry_ids:[E1,E2]}` | multi-entry deep-link popover |

(The `document_overpayment` alert is also what `analyze`/`build-documents` would emit; seeding it directly keeps the browser smoke independent of running `analyze`.)

## better-auth (provisioned at smoke time, not in the D1 seed batch)

- `users` row email `e2e@svhc.local`, `role='admin'` — created by `scripts/e2e/auth.py` via the running app's `POST /api/auth/sign-up/email` then `UPDATE users SET role='admin' …` through `wrangler`. Not part of the synthetic `upsert_tables` batch because better-auth must hash the password through its own endpoint.

## Validation / relationships

- All FKs resolve (TABLE_ORDER insert order; `PRAGMA defer_foreign_keys` in the batch SQL).
- Idempotency: every id is `det_id`-derived → second seed is `INSERT OR REPLACE` over the same ids.
- Synthetic markers (`EXEMPLO`, `2099-01`, `*.svhc.local`, fake CNPJs) satisfy FR-002/SC-005.
