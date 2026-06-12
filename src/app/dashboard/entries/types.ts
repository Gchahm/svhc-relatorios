// Shared row types for the entries feature. Co-located here (rather than inside the
// `EntriesClient` component module) so other feature clients — e.g. the alert detail page —
// can import the types without importing a `"use client"` component module for them.

// One ledger line as rendered by the entries client. Source: GET /api/entries.
// `id` is the persisted text UUID (`entries.id`), delivered as a string by the API — never a
// number; do not coerce it at call sites.
export interface Entry {
    id: string;
    date: string;
    description: string;
    amount: number;
    movementType: string;
    sourceUrl: string;
    period: string;
    category: string;
    subcategory: string;
    vendor: string | null;
    unitCode: string | null;
}

// Shape returned by GET /api/attachment-analyses (one object per analysis). The detail dialog
// consumes this directly and self-fetches its per-page records/images by `id`.
export interface AttachmentAnalysisRow {
    id: string;
    attachmentId: string;
    analyzedAt: number;
    documentType: string | null;
    extractedAmount: number | null;
    amountMatch: boolean | null;
    extractedCnpj: string | null;
    issuerName: string | null;
    vendorMatch: boolean | null;
    extractedDate: string | null;
    dateMatch: boolean | null;
    documentNumber: string | null;
    serviceDescription: string | null;
    error: string | null;
    entryId: string;
    entryDate: string;
    entryDescription: string;
    entryAmount: number;
    entryMovementType: string;
    vendorName: string | null;
    subcategoryName: string | null;
    categoryName: string | null;
}
