/**
 * Pure helpers for `GET /api/attachment-analyses` (feature 045 / TEST-003).
 *
 * The route's pure-extractable pieces are the optional period-scoping decision and the response
 * projection field set. Extracted here so both are unit-testable without the Cloudflare runtime;
 * the route owns the Drizzle query and applies the scope via `where(period ? eq(...) : undefined)`.
 */

/**
 * Whether the list is period-scoped: true iff a non-empty `period` query param is present. Mirrors
 * the route's `where(period ? … : undefined)` truthiness so the scoping behavior is pinned.
 */
export function attachmentAnalysesPeriodScoped(period: string | null | undefined): boolean {
    return typeof period === "string" && period.length > 0;
}

/** The exact key set each attachment-analysis row exposes in the response. */
export const ATTACHMENT_ANALYSIS_RESPONSE_FIELDS = [
    "id",
    "attachmentId",
    "analyzedAt",
    "documentType",
    "extractedAmount",
    "amountMatch",
    "extractedCnpj",
    "issuerName",
    "vendorMatch",
    "extractedDate",
    "dateMatch",
    "documentNumber",
    "serviceDescription",
    "error",
    "entryId",
    "entryDate",
    "entryDescription",
    "entryAmount",
    "entryMovementType",
    "vendorName",
    "subcategoryName",
    "categoryName",
] as const;
