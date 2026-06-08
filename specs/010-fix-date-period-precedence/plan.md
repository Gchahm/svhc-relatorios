# Implementation Plan: Date period-membership precedence

**Branch**: `fix-date-period-precedence` | **Spec**: ./spec.md

## Summary

Make the out-of-period `date` check cash-basis and the date roll-up payment-artifact-aware in
`scripts/analysis/documentos.py`, mirroring the merged amount/issuer roll-up precedence fix (PR #13).
Tighten the `classify-doc-page` prompt for two reading misreads. Stdlib-only Python; no D1 schema
change, no TypeScript.

## Constitution Check

- **III Quality gates**: Python analysis code + a Markdown prompt; no TS touched, so `pnpm lint/format`
  not applicable. Keep changes self-contained and readable.
- **V Simplicity / minimal change**: targeted edits to one seam (`_rollup_document_fields` for the
  date roll-up + a new `date_match` derivation reused in `build_document_analysis` and
  `_fanout_result`). No new module, no new dependency — the date logic is small and lives beside the
  existing helpers.

## Design

### Edits in `documentos.py`

1. **Payment-receipt-preferring date roll-up** in `_rollup_document_fields`: replace
   `result.extracted_date = first_field("data_emissao")` with a precedence helper
   `_pick_document_date(records)` that prefers, in order: a `comprovante`-type page reporting
   `valor_pago` → any `comprovante` page → any page with `valor_pago` populated → a `recibo` page →
   a boleto page → invoice/nfse issue date → any remaining dated page (FR-002). This surfaces the
   settlement/competência date for display, mirroring the amount precedence already in this function.

2. **Cash-basis period membership** via a new `_document_in_period(records, period)` helper used to
   set `date_match` (FR-001/FR-003/FR-004): a document is in period if **any** page's `data_emissao`
   is in the period window (period month or previous month), false if none is, null if no page has a
   date. This replaces `_check_date_in_period(result.extracted_date, period)` at the two call sites so
   a stale/misread date on one page can never *create* an out-of-period flag when another page is
   in-period, while a truly stale document (no in-period date anywhere) still flags.
   `_check_date_in_period` is retained (single-date predicate reused by `_document_in_period`).

3. Apply at both call sites: `build_document_analysis` (single-entry) and `_fanout_result` (shared-NF
   sibling) re-derive `date_match` from the records via `_document_in_period`.

### Prompt tightening: `.claude/skills/classify-doc-page/SKILL.md`

- **Never synthesize a date**: explicit rule that `data_emissao` must be a date *printed on the page*
  (`DD/MM/YYYY`); if no such date is legible, use `null` — never infer/compose one from a partial or
  differently-formatted token (resolves the fabricated `27/01/2026`).
- **Payslip/holerite rule**: on a payroll/holerite/13º/payslip page, `data_emissao` is the **reference
  month / payment date**, NOT the **Data Admissão** hire date (resolves the `11/11/2024` misread).

These two are the `reading` sub-cause and only take effect on the next vision re-classify.

## Verification

Deterministic (no image re-read): replay the persisted 2025-12 extractions through the new precedence
to confirm 25/27 false mismatches flip and zero regressions across all 125 dated documents
(documented in the spec's Success Criteria; the validation harness mirrors the persisted
`analysis_records[].response`). Then re-run the scoped chain for the affected documents:
`apply-extractions` → `analyze` → `mismatches`. The two `reading` cases flip only after a re-classify
with the tightened prompt.
