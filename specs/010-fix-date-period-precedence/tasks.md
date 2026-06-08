# Tasks: Date period-membership precedence

- [x] T001 `documentos.py`: add `_pick_document_date(records)` — payment-receipt-preferring date
  precedence (comprovante-with-`valor_pago` → comprovante → any `valor_pago` page → recibo → boleto →
  invoice/nfse → any dated page); use it in `_rollup_document_fields` to set `extracted_date`
  (FR-002), mirroring the amount precedence already in that function.
- [x] T002 `documentos.py`: add `_document_in_period(records, period)` — cash-basis membership: true
  if ANY page `data_emissao` is in the period window, false if none, null if no dated page (reuses
  `_check_date_in_period` as the single-date predicate). Replace the
  `_check_date_in_period(result.extracted_date, period)` call in `build_document_analysis` and the
  `_check_date_in_period(new.extracted_date, period)` call in `_fanout_result` with
  `_document_in_period(...records, period)` (FR-001/FR-003/FR-004/FR-005).
- [x] T003 `.claude/skills/classify-doc-page/SKILL.md`: add two date rules — (a) never synthesize a
  `data_emissao`; transcribe only a date printed on the page or use `null`; (b) on payroll/holerite/
  payslip pages `data_emissao` is the reference month / payment date, never the Data Admissão hire
  date (FR-006; addresses the two `reading` misreads on the next re-classify).
- [x] T004 Verify against persisted 2025-12 extractions: 25/27 false `date` mismatches reconcile via
  code with zero regressions across all 125 dated documents (SC-001/SC-003/SC-004); the 2 remaining
  are the `reading` cases needing re-classify (SC-002); note the review-`true` boundary case
  `fba6bec0` also reconciles (not special-cased). Then re-run the scoped chain
  (`apply-extractions` → `analyze` → `mismatches`) for the affected documents.
