/**
 * Over/within/under-total status for a document, mirroring the Python pipeline's
 * reconciliation tolerance (`scripts/analysis/nf_groups.py`: within 5% relative OR
 * R$0.05 absolute → reconciled). Shared by /api/documents and /api/documents/[id].
 */
export type DocumentStatus = "over" | "within" | "under" | "unknown";

const REL_TOL = 0.05;
const ABS_TOL = 0.05;

export function documentStatus(sumEntries: number, totalValue: number | null): DocumentStatus {
    if (totalValue === null || totalValue <= 0) return "unknown";
    const diff = Math.abs(sumEntries - totalValue);
    if (diff <= ABS_TOL || diff / totalValue < REL_TOL) return "within";
    return sumEntries > totalValue ? "over" : "under";
}
