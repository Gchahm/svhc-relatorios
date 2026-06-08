# Tasks: Amount roll-up precedence

**Branch**: `fix-rollup-precedence-amount` | **Plan**: ./plan.md

- [ ] **T001** Add `_pick_payment_amount(payment_recs)` helper to `scripts/analysis/documentos.py`,
  ranking payment proofs like `_pick_document_date` (comprovante-with-valor_pago > comprovante >
  any valor_pago > valor_total), skipping non-positive values. Identical to current behavior for a
  single payment proof. (FR-001, FR-006)
- [ ] **T002** Add `_sum_distinct_invoices(invoice_recs)` helper that sums distinct invoice pages'
  `valor_total`, de-duplicated on (`numero_documento`, `valor_total`); returns None if fewer than 2
  distinct. (FR-002)
- [ ] **T003** Rewire the amount block of `_rollup_document_fields`: payment proofs via
  `_pick_payment_amount`; if no payment/boleto artifact, try `_sum_distinct_invoices` before the
  single-invoice net/gross fallback. Leave boleto, single-invoice net/gross, tolerance, and group
  reconciliation paths unchanged. (FR-001..FR-006)
- [ ] **T004** Deterministic validation harness: replay persisted 2025-12 extractions through the new
  roll-up for the 3 target docs and assert each flips to `amount_match` true; scan all analyzed docs
  for new amount mismatches (zero regressions). (SC-001, SC-002)
- [ ] **T005** Scoped re-run: `apply-extractions` → `analyze` → `mismatches --document-id <3 ids>`
  confirms the 3 are gone; full-period `mismatches` confirms no new amount mismatch. (SC-001..SC-004)
