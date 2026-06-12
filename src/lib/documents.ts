/**
 * Over/within/under-total status for a document, mirroring the Python pipeline's
 * reconciliation tolerance (`scripts/analysis/nf_groups.py`: within 5% relative OR
 * R$0.05 absolute → reconciled). Shared by /api/documents and /api/documents/[id].
 */
export type DocumentStatus = "over" | "within" | "under" | "unknown";

// DRIFT GUARD (IMP-006 / issue #43): this over/within/under decision is mirrored in Python by
// `reconcile_group` in `scripts/analysis/nf_groups.py` (AMOUNT_REL_TOL/AMOUNT_ABS_TOL), which
// drives `amount_match`, shared-NF reconciliation, and the `document_overpayment` alert. The two
// MUST stay in lockstep — a divergence makes this badge and the alert that created it disagree.
// They are bound by the shared fixture `scripts/analysis/reconciliation_contract.json` and
// cross-language contract tests (`src/lib/documents.test.mjs` + `scripts/tests/test_reconciliation_contract.py`):
// change a constant or comparison here and you MUST update nf_groups.py AND the fixture, or a
// contract test fails.
const REL_TOL = 0.05;
const ABS_TOL = 0.05;

export function documentStatus(sumEntries: number, totalValue: number | null): DocumentStatus {
    if (totalValue === null || totalValue <= 0) return "unknown";
    const diff = Math.abs(sumEntries - totalValue);
    if (diff <= ABS_TOL || diff / totalValue < REL_TOL) return "within";
    return sumEntries > totalValue ? "over" : "under";
}
