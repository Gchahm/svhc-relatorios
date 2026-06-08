# Feature Specification: Amount roll-up precedence (fix bundled-artifact / installment false positives)

**Branch**: `fix-rollup-precedence-amount`
**Created**: 2026-06-08
**Status**: Draft
**Origin**: Self-improving classification loop — fix step for 3 `false` `amount` mismatches in period 2025-12

## Summary

The document-classification analysis flags an `amount` mismatch when the document-level amount does
not match the ledger entry's amount (within tolerance). For period 2025-12 the vision-review step
judged **3** `amount` mismatches as **false positives** (system faults, not real findings). All three
share one root cause area — `rollup-precedence`: the document-level amount used for `amount_match` is
derived wrongly when a single document **bundles multiple artifacts** (invoice + payment receipt) or
**installments** (a parcela of a larger agreement).

The condominium frequently attaches, in one document, an invoice or recibo bearing a **gross /
agreement total** alongside a **payment artifact** (a bank/PIX *comprovante de pagamento*) that
records the **actual cash settled** for the booked entry. The meaningful amount for a cash-basis
ledger entry is the settled value on the genuine payment receipt — not the upstream gross headline.

The three concrete shapes (all single-document NF groups, so the shared-NF group reconciliation in
`nf_groups.py` does not apply — they go through the plain per-document amount comparison):

1. **Two distinct invoice pages, no payment artifact.** A document holds NF 000.046.576 (R$1.097,40,
   p1) and NF 000.046.577 (R$465,00, p2) — two separate DANFE invoices from the same issuer. The
   roll-up took only p1's `valor_total` (R$1.097,40); the ledger is R$1.562,40 = 1.097,40 + 465,00,
   i.e. the **sum of the two invoice pages**.
2. **Recibo gross vs. settlement comprovante.** A document bundles a RECIBO with the full
   3-installment agreement total (R$30.000) on p1 plus a Sicredi PIX *comprovante de pagamento* for
   this parcela 3/3 of R$10.000 (p3, matches the ledger). The roll-up surfaced the recibo's headline
   gross (R$30.000) instead of the genuine payment artifact's `valor_pago` (R$10.000).
3. **Gross NFS-e vs. boleto comprovante.** An entry is installment 1/3 (ledger R$362,50). The NFS-e
   page carries the gross competência total R$1.087,50 (= 3 × 362,50) and is mislabeled as a payment
   proof because it exposes a headline `valor_pago`; p3 is a genuine Sicredi *comprovante de pagamento
   de boleto* for the parcela paid (R$362,50, matches the ledger). The roll-up used the gross
   R$1.087,50 instead of the genuine payment receipt's R$362,50.

Cases 2 and 3 share a single principled sub-cause: **among payment-proof pages, a genuine settlement
comprovante (an actual bank/PIX transaction receipt) must outrank a recibo / NFS-e that merely carries
a headline `valor_pago`.** This mirrors the date roll-up's already-merged `_pick_document_date`
ranking (comprovante-with-`valor_pago` > comprovante > `valor_pago` > recibo). Case 1 is a distinct
sub-cause: a multi-invoice document with no payment artifact must **sum** its distinct invoice pages.

## User Scenarios & Testing

### Primary user story

As a fiscal auditor reviewing the condominium's December spending, I want an `amount` mismatch to fire
**only** when the document's amount genuinely differs from the ledger entry — i.e. when the cash
actually settled (or, absent a payment receipt, the total of the document's invoices) does not match
the booked amount — so that a document bundling a gross agreement total plus the parcela's real
payment receipt, or splitting a charge across two invoice pages, does not bury me in false positives.

### Acceptance scenarios

1. **Given** a document with two distinct invoice pages (DANFE R$1.097,40 and DANFE R$465,00) and no
   payment artifact, ledger amount R$1.562,40, analyzed for `2025-12`, **then** `amount_match` is true
   (the document amount is the sum of the invoice pages' `valor_total`).
2. **Given** a document bundling a RECIBO headline gross R$30.000 (p1) and a Sicredi PIX comprovante
   reporting `valor_pago` R$10.000 (p3), ledger amount R$10.000, analyzed for `2025-12`, **then**
   `amount_match` is true and the document amount is the comprovante's paid value (R$10.000), not the
   recibo gross.
3. **Given** a document whose NFS-e page carries a gross R$1.087,50 (mislabeled as a payment proof via
   a headline `valor_pago`) and whose boleto comprovante page reports the paid parcela R$362,50,
   ledger amount R$362,50, analyzed for `2025-12`, **then** `amount_match` is true and the document
   amount is the genuine comprovante's paid value (R$362,50).
4. **Given** a document whose genuine payment receipt records a paid value that truly differs from the
   ledger amount (beyond tolerance), analyzed for `2025-12`, **then** `amount_match` stays false and
   the mismatch still surfaces (detection preserved).
5. **Given** a single-document case that participates in a shared-NF group, **then** the group
   reconciliation in `nf_groups.py` continues to own the amount decision (sibling sum vs NF gross
   total) and is not double-counted by the per-document precedence change.

### Edge cases

- No page yields any positive amount → `extracted_amount` stays null (no comparison), as today.
- A single invoice page (no payment artifact) → `extracted_amount` is that page's net/gross as today
  (unchanged behavior for single-invoice documents).
- A document with a single payment-proof page → that page's `valor_pago` wins as today (no behavior
  change when there is exactly one payment proof).
- A spurious `valor_pago: 0.0` MUST NOT win and force the amount to zero when a real value is present
  elsewhere (preserved from current code).

## Requirements

### Functional Requirements

- **FR-001**: When a document has **more than one** payment-proof page, the document-level amount used
  for `amount_match` MUST prefer the **genuine settlement comprovante**'s paid value over a recibo /
  invoice-derived headline `valor_pago`. The preference order among payment-proof pages is: a
  `comprovante`-type page reporting `valor_pago` → any `comprovante` page's `valor_pago` → any
  payment-proof page's `valor_pago` → `valor_total`. This mirrors the `_pick_document_date` ranking.
- **FR-002**: When a document has **no** payment artifact (no payment-proof and no boleto page) but
  **multiple distinct invoice pages** (distinguished by content — different `numero_documento` and/or
  `valor_total`), the document amount MUST be the **sum** of the distinct invoice pages' `valor_total`,
  not a single page's value. A single invoice page (or repeated identical invoice pages) keeps its
  current single-value behavior.
- **FR-003**: Detection MUST be preserved: a document whose genuine payment value (or invoice sum)
  differs from the ledger entry beyond tolerance MUST still produce `amount_match` false and surface
  the mismatch. The fix re-orders/aggregates which value is chosen; it does not loosen the tolerance.
- **FR-004**: The change MUST compose with the shared-NF group reconciliation (`nf_groups.py`):
  documents in a multi-entry group keep their group reconciliation (sibling sum vs NF gross total);
  the per-document precedence change applies to the single-document comparison path only and MUST NOT
  double-count. `nf_total_for_reconciliation` (gross `valor_total` preference) is unchanged.
- **FR-005**: The change MUST be stdlib-only Python within `scripts/analysis/` and apply uniformly to
  single-entry documents and to shared-NF siblings (the fan-out copies the rolled-up amount).
- **FR-006**: The existing amount precedence for the common single-payment-proof and single-invoice
  documents MUST be unchanged (no regressions on the documents that already match).

### Key Entities

- **Payment-proof page**: a page whose artifact role is `payment_proof` — a `comprovante`/`recibo`
  page or any page reporting `valor_pago`. A *genuine settlement comprovante* is the subset of these
  whose `tipo_documento` is `comprovante` (an actual bank/PIX transaction receipt), distinguished from
  a recibo or an invoice page that merely exposes a headline `valor_pago`.
- **Distinct invoice page**: an `invoice`/`nfse` page identified by its `numero_documento` /
  `valor_total`; two invoice pages with different NF numbers are distinct line items to be summed.
- **Document amount** (`extracted_amount`): the rolled-up value compared against the ledger entry,
  within the existing 5% relative tolerance.

## Success Criteria

- **SC-001**: All 3 false `amount` mismatches enumerated for period 2025-12 are resolved
  (`amount_match` becomes true) by the **code** change alone, verifiable against the persisted
  extractions in `data/scrape/2025-12.json` without re-reading images.
- **SC-002**: No NEW `amount` mismatch appears across the analyzed documents in 2025-12 that was not
  present before the change (zero regressions) — verified by re-running `analyze` + `mismatches` for
  the period.
- **SC-003**: A document whose genuine paid value (or invoice sum) differs from the ledger beyond
  tolerance still flags `amount_match` false (detection preserved).
- **SC-004**: Shared-NF multi-entry groups keep their reconciliation outcome unchanged (the
  per-document precedence change does not alter group decisions).

## Assumptions

- The extraction schema captures `valor_total`, `valor_liquido`, `valor_pago`, `tipo_documento`, and
  `papel_artefato` per page (frozen field set); the genuine settlement comprovante is identified by
  `tipo_documento == "comprovante"`, mirroring `_pick_document_date`'s use of the same signal.
- A multi-invoice document's pages carry distinct `numero_documento` and `valor_total` values when
  they are separate line items; summing identical-content invoice pages is avoided by de-duplicating
  on (`numero_documento`, `valor_total`) so a re-scanned duplicate of one invoice does not double.
- The 5% relative / R$0.05 absolute tolerances are unchanged; only the chosen/aggregated value
  changes.
- All 3 affected documents are single-document NF groups, so the change is exercised on the
  per-document comparison path; the shared-NF reconciliation path is untouched.
