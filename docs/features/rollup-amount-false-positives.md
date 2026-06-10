# Roll-up `amount_match` false positives: record-selection & invoice↔entry cardinality

> Follow-up to `003-vlm-analyze-all-pages`. Overlaps SCOPE Phase 2 (cross-reference
> reconciliation). Self-contained — can feed `/speckit specify` or a direct PR for the
> record-selection part.

## Context

After `003-vlm-analyze-all-pages` (multi-page analysis + heterogeneity-aware roll-up) and its
`0.0`-short-circuit fix, a fuller live run on `2025-12` (126 docs) showed that **all 10
`amount_match = 0` results are false positives** — none are real discrepancies. The correct value
is present in the per-page records; the document-level roll-up just doesn't select/aggregate it
correctly. Two distinct causes remain (the `0.0` short-circuit was already fixed in PR #1).

## Problem A — first-record-of-role wins (record selection)

`_rollup_attachment_fields` (`scripts/analysis/attachments.py`) picks the **first** record of
the preferred role, not the one matching the entry. When a document bundles several payment
records, the wrong one wins:

| entry amount | extracted | a record holds       |
| ------------ | --------- | -------------------- |
| R$ 10000     | 30000     | `valor_pago: 10000`  |
| R$ 362.50    | 1087.50   | `valor_pago: 362.50` |

The entry amount is known at roll-up time (`entry_amount`), so selection could prefer the
record whose value matches the entry (within the existing 5% tolerance) before falling back to
the precedence order.

**Caution (audit-tool semantics):** simply switching validation to "does _any_ extracted amount
match the entry?" would clear these cases but risks **false negatives** — hiding a genuine
discrepancy is worse than a false positive for a fraud/forgery tool. Any "match-aware selection"
must keep a real mismatch visible (e.g. record _which_ artifact matched, and still surface when
none does). Treat this as a deliberate design decision, not a blind patch.

## Problem B — invoice ↔ entry cardinality (Phase 2 reconciliation)

The one-document-per-entry model breaks when invoices and entries aren't 1:1:

- **One invoice spanning multiple entries:** entries `6430 + 452 + 212.32 + 66` each extract
  `7160.32` — those four sum to exactly 7160.32 (a single NFS-e covering four line-item entries,
  with the full invoice attached to each entry).
- **Multiple invoices per entry:** entry `1562.40` has two invoice records `465.00 + 1097.40`
  that should be **summed** to match.

These are **not** fixable by record-selection alone — they need cross-artifact / cross-entry
reconciliation (matching invoice line items to entries, summing where appropriate). This is SCOPE
**Phase 2** (cross-reference validation) and likely also touches the
`scraper-multiple-documents-per-entry` work.

## Goal

- **A (in this ticket / near-term):** the roll-up's `amount_match` stops firing on documents
  where a per-page record already matches the entry, **without** introducing false negatives.
- **B (Phase 2):** reconcile invoice↔entry cardinality (split/summed amounts) so multi-entry
  invoices and multi-invoice entries validate correctly.

## Out of scope

- The page-extraction / per-page-record machinery itself (done in `003-vlm-analyze-all-pages`).
- The `0.0` short-circuit (already fixed in PR #1).

## Acceptance (Problem A)

- For a document with multiple payment records where one matches the entry amount, the roll-up
  selects the matching record and `amount_match` is true.
- A document where **no** record matches the entry still reports `amount_match = 0` (no false
  negative introduced) and ideally records which artifact values were considered.
- The `2025-12` selection cases (entries 10000 and 362.50 above) flip from false mismatch to match.
