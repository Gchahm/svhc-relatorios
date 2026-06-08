# Implementation Plan: Amount roll-up precedence

**Branch**: `fix-rollup-precedence-amount` | **Spec**: ./spec.md

## Summary

Make the document-level amount roll-up in `scripts/analysis/documentos.py` prefer the genuine
settlement comprovante among multiple payment proofs, and sum distinct invoice pages when no payment
artifact is present. Mirrors the merged amount/issuer roll-up precedence (PR #13) and the date roll-up
ranking (PR #14). Stdlib-only Python; no D1 schema change, no TypeScript. All 3 affected docs are
single-document NF groups, so the change targets the per-document comparison path; the shared-NF
`nf_groups.py` reconciliation is untouched.

## Constitution Check

- **III Quality gates**: Python analysis code only; no TS touched, so `pnpm lint/format` not
  applicable. Keep changes self-contained and readable.
- **V Simplicity / minimal change**: one targeted edit to the amount block of `_rollup_document_fields`
  plus a small `_pick_payment_amount` helper that mirrors the existing `_pick_document_date` ranking.
  No new module, no new dependency.

## Design

### Edits in `documentos.py` — only the amount block of `_rollup_document_fields`

The current amount precedence is:

```
amount = pick(payment_recs, "valor_pago", "valor_total")   # first payment proof wins
if amount is None: amount = pick(boleto_recs, "valor_total", "valor_pago")
if amount is None: amount = pick(invoice_recs, "valor_liquido")
if amount is None: amount = pick(invoice_recs or parsed_records, "valor_total")
```

The bug: `pick(payment_recs, ...)` returns the **first** payment-proof page, so a recibo/NFS-e
headline gross beats a genuine comprovante (cases 2 and 3), and `pick(invoice_recs, "valor_total")`
returns only the **first** invoice page (case 1).

Two changes:

1. **Rank payment proofs (FR-001).** Replace `pick(payment_recs, "valor_pago", "valor_total")` with a
   helper `_pick_payment_amount(payment_recs)` that, when there is **more than one** payment proof,
   prefers the genuine settlement comprovante's paid value using the same ranking as
   `_pick_document_date`:
   - rank 0: `tipo_documento == "comprovante"` **and** positive `valor_pago` → its `valor_pago`
   - rank 1: `tipo_documento == "comprovante"` → its `valor_pago` then `valor_total`
   - rank 2: any payment-proof page with positive `valor_pago` → its `valor_pago`
   - rank 3: any payment-proof page `valor_total`

   With exactly one payment proof the behavior is identical to today (its `valor_pago` then
   `valor_total`), so the common single-receipt document is unchanged (FR-006). Non-positive values
   are skipped (preserves the `valor_pago: 0.0` guard).

2. **Sum distinct invoice pages when no payment artifact (FR-002).** When `payment_recs` and
   `boleto_recs` are both empty and there are **multiple distinct** invoice pages, set the amount to
   the **sum** of the distinct invoice pages' `valor_total`. "Distinct" = de-duplicated on
   (`numero_documento`, `valor_total`) so a re-scanned duplicate of one invoice is not double-counted.
   A single distinct invoice keeps the current `valor_liquido` → `valor_total` fallback (so the
   single-invoice net-vs-gross behavior is unchanged). The net fallback only applies to the
   single-invoice case; multi-invoice line-item splits are summed on gross `valor_total` (entries are
   gross allocations, matching `nf_total_for_reconciliation`'s gross preference).

No change to `boleto_recs` handling, to the invoice net/gross fallback for single invoices, to
`nf_total_for_reconciliation`, to `_apply_group_amount_match`, or to the tolerance in
`build_document_analysis`. The fan-out (`_fanout_result`) copies `extracted_amount`, so shared-NF
siblings inherit the corrected roll-up but their `amount_match` is still owned by group reconciliation
(FR-004).

### No prompt change

Unlike the date fix, all 3 amount cases flip from the **code alone** — the per-page extractions are
already correct (the genuine comprovante's `valor_pago` and both invoice `valor_total`s are persisted
in `data/scrape/2025-12.json`). The roll-up simply chose the wrong page. No `classify-doc-page`
re-classify is required.

## Verification

Deterministic (no image re-read): replay the persisted 2025-12 extractions through the new precedence
to confirm all 3 false mismatches flip and there are zero regressions across the analyzed documents.
Then re-run the scoped chain for the affected documents: `apply-extractions` → `analyze` →
`mismatches --document-id <ids>`, plus a full-period `mismatches` to confirm no new amount mismatch.
