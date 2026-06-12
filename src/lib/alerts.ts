/**
 * Shared alert type → human-readable label map (IMP-010 / issue #47).
 *
 * Alert `type` values are machine identifiers (`snake_case`) produced by the analysis/scraper
 * pipeline. They were rendered raw in the alerts list Type filter and on the alert detail page,
 * which read inconsistently next to the human-labeled Severity/Status surfaces. This module is the
 * single source of truth for the friendly label so the filter, the detail page, and any future
 * type-rendering surface can't drift.
 *
 * `alertTypeLabel` is pure and total — it never throws for any string input — so an unexpected or
 * newly-added pipeline type degrades to a readable `snake_case → Sentence case` fallback rather than
 * leaking a raw identifier (FR-003/FR-007).
 */

/**
 * Curated labels for every alert type the pipeline currently emits (see
 * specs/038-alert-type-labels/data-model.md). Any type not listed here falls back to the generic
 * transform in `alertTypeLabel`, so this map need not stay perfectly exhaustive to keep every
 * surface readable.
 */
export const ALERT_TYPE_LABELS: Record<string, string> = {
    attachment_amount_mismatch: "Attachment amount mismatch",
    attachment_vendor_mismatch: "Attachment vendor mismatch",
    attachment_date_mismatch: "Attachment date mismatch",
    attachment_page_error: "Attachment page error",
    attachment_not_downloaded: "Attachment not downloaded",
    document_overpayment: "Document overpayment",
    duplicate_billing: "Duplicate billing",
    duplicate_entry: "Duplicate entry",
    negative_credit: "Negative credit",
    large_expense_no_attachment: "Large expense without attachment",
    unit_delinquency: "Unit delinquency",
    subtotal_mismatch: "Subtotal mismatch",
    balance_opening_mismatch: "Opening balance mismatch",
    balance_month_mismatch: "Month balance mismatch",
    balance_accumulated_mismatch: "Accumulated balance mismatch",
    entries_revenue_mismatch: "Entries vs. revenue mismatch",
    entries_expenses_mismatch: "Entries vs. expenses mismatch",
    portal_row_vanished: "Portal row vanished",
    scrape_inconsistency: "Scrape inconsistency",
    new_vendor: "New vendor",
    vendor_concentration: "Vendor concentration",
    category_growth_outlier: "Category growth outlier",
    subcategory_above_average: "Subcategory above average",
    missing_recurring_subcategory: "Missing recurring subcategory",
    missing_period: "Missing period",
};

/**
 * Human-readable label for an alert type. Returns the curated label when known; otherwise a generic
 * `snake_case → Sentence case` transform (underscores → spaces, first character upper-cased). Empty
 * string in → empty string out. Never throws.
 */
export function alertTypeLabel(type: string): string {
    const curated = ALERT_TYPE_LABELS[type];
    if (curated) return curated;
    const spaced = type.replace(/_/g, " ");
    if (spaced.length === 0) return "";
    return spaced.charAt(0).toUpperCase() + spaced.slice(1);
}
