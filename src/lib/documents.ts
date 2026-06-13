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

/**
 * Where a document's reconciliation total (`documents.total_value`) came from. Lets the document
 * detail UI explain a figure ("R$800 from page p3, invoice gross") instead of presenting it as a
 * mystery — feature 048.
 *
 * - `gross`  — the invoice GROSS `valor_total` extracted from a specific page (`sourcePageLabel`).
 * - `rollup` — the analysis roll-up `extracted_amount` fallback (no confident page gross).
 * - `none`   — no AI total could be derived.
 */
export type TotalSource = "gross" | "rollup" | "none";

export interface ReconciliationTotal {
    value: number | null;
    source: TotalSource;
    sourcePageLabel: string | null;
}

export interface ExtractionPage {
    pageLabel: string | null;
    /** The page's extracted `valor_total` — a number, a BRL string ("R$ 800,00"), null, or junk. */
    valorTotal: unknown;
}

// DRIFT GUARD (feature 048): this selection MUST mirror `nf_total_for_reconciliation` in
// `scripts/analysis/attachments.py` (prefer the first confident invoice gross `valor_total`, else
// the rolled-up `extracted_amount`, else none) and the BRL parsing of `_parse_brl_value` in the
// same file. The pipeline computes `documents.total_value` with that rule, so the UI attribution
// here and the persisted value would silently disagree if one side changed without the other.
// Change this and you MUST update `attachments.py` (and vice versa).

/** Parse a Brazilian currency value (number or string) to a finite float, mirroring `_parse_brl_value`. */
function parseBrlValue(value: unknown): number | null {
    if (value === null || value === undefined) return null;
    if (typeof value === "number") return Number.isFinite(value) ? value : null;
    let text = String(value).trim().replace(/R\$/g, "").trim();
    text = text.replace(/[^\d,.]/g, "");
    if (text.includes(",")) text = text.replace(/\./g, "").replace(",", ".");
    if (text === "") return null;
    const parsed = Number(text);
    return Number.isFinite(parsed) ? parsed : null;
}

/**
 * The reconciliation total for ONE analysis: the first page (in the given order) whose `valor_total`
 * parses to a finite value `> 0` wins as `gross`; otherwise the finite `rollup` (`extracted_amount`)
 * as `rollup`; otherwise `none`. `pages` MUST be ordered the way the total is attributed (by page
 * index ascending). Mirrors `nf_total_for_reconciliation`.
 */
export function selectReconciliationTotal(pages: ExtractionPage[], rollup: number | null): ReconciliationTotal {
    for (const page of pages) {
        const gross = parseBrlValue(page.valorTotal);
        if (gross !== null && gross > 0) {
            return { value: gross, source: "gross", sourcePageLabel: page.pageLabel };
        }
    }
    if (rollup !== null && Number.isFinite(rollup)) {
        return { value: rollup, source: "rollup", sourcePageLabel: null };
    }
    return { value: null, source: "none", sourcePageLabel: null };
}
