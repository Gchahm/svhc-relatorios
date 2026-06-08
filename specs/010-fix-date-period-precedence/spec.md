# Feature Specification: Date period-membership precedence (fix out-of-period false positives)

**Branch**: `fix-date-period-precedence`
**Created**: 2026-06-08
**Status**: Draft
**Origin**: Self-improving classification loop — fix step for 27 `false` `date` mismatches in period 2025-12

## Summary

The document-classification analysis flags a `date` mismatch when the document's date does not fall
within the period (the period month or the previous month). For period 2025-12 the vision-review step
judged **27** of the `date` mismatches as **false positives** (system faults, not real findings).

The condominium books on a **cash basis**: a single document commonly bundles an invoice (NF-e /
DANFE / NFS-e) issued in an **earlier** month plus a **payment artifact** — a boleto, a PIX, or a
Sicredi/Sicoob *comprovante de pagamento* — settled **inside** the period. Example: an invoice issued
`23/10/2025` paid by a comprovante on `23/12/2025`, booked to the ledger as a December entry.

Two fixable sub-causes produce the false positives:

1. **Roll-up precedence anchors on the invoice issue date.** The document-level roll-up
   (`_rollup_document_fields`) sets `extracted_date` from the first record's `data_emissao` with the
   **invoice/nfse record prioritized**, so the upstream issue date (e.g. 23/10) is surfaced for the
   period check instead of the in-period payment date present on the comprovante page (23/12). The
   period membership test (`_check_date_in_period`) then sees the issue month and flags out-of-period.
   This is the principled mirror of the already-merged amount/issuer roll-up precedence fix (PR #13),
   which prefers the payment artifact.
2. **Two reading misreads.** Independently of the roll-up, two documents carry a wrong date on the
   page itself:
   - a **fabricated** `27/01/2026` that appears on no page (every legible page date is in December;
     the receipt reads "Emitido em 27/12/2025") — the reader synthesized a date;
   - a **payslip** where the reader captured the **Data Admissão** hire date `11/11/2024` instead of
     the reference month (11/2025) / payment date (05/12/2025).

   These flip only after a vision **re-classify** with a tightened `classify-doc-page` prompt.

## User Scenarios & Testing

### Primary user story

As a fiscal auditor reviewing the condominium's December spending, I want a `date` ("out-of-period")
mismatch to fire **only** when the document genuinely does not belong to the period — i.e. when none
of its artifacts (payment receipt, boleto vencimento, or invoice issue) bears an in-period date — so
that the normal accounting lag between an invoice issued in an earlier month and its in-period
payment does not bury me in false positives.

### Acceptance scenarios

1. **Given** a document bundling an NF-e issued `23/10/2025` and a Sicredi comprovante paid
   `23/12/2025`, analyzed for period `2025-12`, **then** `date_match` is true (the in-period payment
   date establishes period membership) and the surfaced `extracted_date` is the payment date.
2. **Given** a document whose only in-period date is a boleto **vencimento** `10/12/2025` (invoice
   issued `03/10/2025`), analyzed for `2025-12`, **then** `date_match` is true.
3. **Given** a document where the genuine payment comprovante (a `comprovante` page reporting
   `valor_pago`) is dated `15/12/2025` while another receipt-like page carries a stale `11/12/2023`
   date, analyzed for `2025-12`, **then** `date_match` is true and the surfaced date is the in-period
   payment date — a stale receipt date never *creates* an out-of-period flag.
4. **Given** a document whose every page date is outside the period and previous month (no in-period
   payment, vencimento, or issue date anywhere), analyzed for `2025-12`, **then** `date_match` stays
   false and the mismatch still surfaces (detection preserved).
5. **Given** a payslip whose only true in-period signal is the payment/reference date, **when** the
   reader captures that date (after the prompt tightening) instead of the Data Admissão hire date,
   **then** `date_match` is true on re-classify.
6. **Given** a receipt that shows "Emitido em 27/12/2025" and no `DD/MM/YYYY` competência field,
   **when** the reader transcribes only dates actually printed on the page (after the prompt
   tightening) and never synthesizes one, **then** no fabricated `27/01/2026` appears.

### Edge cases

- No page yields any date → `date_match` stays null (no comparison), as today.
- A document with only an invoice page (no payment artifact) → `extracted_date` falls back to the
  invoice issue date and `date_match` reflects whether that issue date is in period (unchanged
  behavior for invoice-only documents).
- A stale date on a non-payment page MUST NOT override an in-period date elsewhere in the document
  (no new out-of-period flag from a misread/old receipt date).

## Requirements

### Functional Requirements

- **FR-001**: Period membership (`date_match`) MUST be cash-basis: a document belongs to the period if
  **any** of its parsed page records carries a date (`data_emissao`) that falls within the period
  month or the immediately previous month. It is false only when no page date is in that window, and
  null when no page carries a date.
- **FR-002**: The document-level `extracted_date` roll-up MUST prefer the **payment-receipt** date
  over the upstream invoice issue date, mirroring the amount/issuer roll-up precedence (PR #13). The
  preference order is: a `comprovante`-type page reporting `valor_pago` → any `comprovante` page → any
  page reporting `valor_pago` → a `recibo` page → a boleto page → the invoice/nfse issue date → any
  remaining dated page.
- **FR-003**: Detection MUST be preserved: a document whose pages carry no in-period date (truly stale
  / out-of-period) MUST still produce `date_match` false and surface the mismatch.
- **FR-004**: A stale or misread date on a non-payment page MUST NOT, by itself, create a new
  out-of-period flag when another page of the same document carries an in-period date (no regressions).
- **FR-005**: The change MUST apply uniformly to single-entry documents and to shared-NF siblings (the
  fan-out path re-derives `date_match`), and MUST be stdlib-only Python within `scripts/analysis/`.
- **FR-006**: The `classify-doc-page` prompt MUST be tightened so the reader (a) never **synthesizes**
  a `data_emissao` not printed on the page (use `null` when no date is legible), and (b) on a
  **payslip / holerite / payroll** document captures the **reference month / payment date**, never the
  **Data Admissão** hire date, as `data_emissao`.

### Key Entities

- **Page record date** (`data_emissao`): the date captured per page — an invoice issue date, a boleto
  vencimento, or a payment-receipt transaction date, depending on the page's role.
- **Payment-receipt page**: a `comprovante`/`recibo` page or any page reporting `valor_pago` — the
  artifact that establishes the in-period settlement date.
- **Period window**: the period month plus the immediately previous month (unchanged from today).

## Success Criteria

- **SC-001**: 25 of the 27 false `date` mismatches enumerated for period 2025-12 are resolved
  (`date_match` becomes true) by the **code** change alone, verifiable against the persisted
  extractions without re-reading images.
- **SC-002**: The remaining 2 false mismatches (the two `reading` misreads) are resolved after a
  vision **re-classify** with the tightened prompt; they are correctly identified as needing
  re-classify (not code-flippable).
- **SC-003**: No NEW out-of-period `date` mismatch appears across the 125 dated documents in 2025-12
  that was not present before the change (zero regressions) — in particular, the stale-receipt
  document `47df0450` (in-period DANFE 15/12/2025 + stale recibo 11/12/2023) stays in-period.
- **SC-004**: A document with no in-period date on any page still flags out-of-period (detection
  preserved).

## Assumptions

- The extraction schema captures a single `data_emissao` per page (frozen field set); a payment-proof
  page's `data_emissao` is its payment/transaction date, a boleto's is its vencimento — so preferring
  the payment-receipt page's date surfaces the settlement/competência date without a new schema field.
- The period window (period month + previous month) is unchanged; only the *choice of which page date
  anchors the document* and the *any-page membership* semantics change.
- The review-`true` boundary finding `fba6bec0` (Oct-issued, Dec-paid) is structurally identical to
  the false cluster and will also reconcile under the principled rule. This is a likely review
  mislabel; it is **noted, not special-cased**. Detection is not weakened for documents that truly
  have no in-period payment artifact.
