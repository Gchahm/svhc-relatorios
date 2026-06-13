/**
 * Pure metadata helpers for the alerts surface (extracted from `alerts.tsx` — feature 045 /
 * TEST-003). These derive auditing-evidence routing from an alert's (untyped JSON) `metadata`:
 * the affected ledger entries, the per-entry deep link, and the referenced document.
 *
 * They live in a `.ts` (not the `"use client"` `.tsx`) so they can be unit-tested with `node:test`
 * (Node strips types from `.ts` but cannot import `.tsx`). `alerts.tsx` re-exports them, so its
 * public surface is unchanged. Pure and defensive: malformed/absent metadata yields the empty
 * result rather than throwing.
 */

/**
 * Entry ids an alert concerns. Covers both the per-attachment mismatch alerts (single `entry_id`)
 * and the entry-level alerts that store an `entry_ids` array (duplicate_billing, duplicate_entry,
 * negative_credit, large_expense_no_attachment). Period/category-level alerts have neither → `[]`.
 */
export function affectedEntryIds(metadata: string | null): string[] {
    if (!metadata) return [];
    try {
        const meta = JSON.parse(metadata) as { entry_ids?: unknown; entry_id?: unknown };
        if (Array.isArray(meta.entry_ids)) {
            return meta.entry_ids.filter((v): v is string => typeof v === "string");
        }
        if (typeof meta.entry_id === "string") return [meta.entry_id];
        return [];
    } catch {
        return [];
    }
}

/** Deep link to the entries page focused on one entry, with the detail dialog auto-opened. */
export function entryHref(period: string, entryId: string): string {
    return `/dashboard/entries?period=${encodeURIComponent(period)}&entry=${encodeURIComponent(entryId)}`;
}

/** The document an alert references (document_overpayment), for a cross-link to its detail page. */
export function referencedDocumentId(metadata: string | null): string | null {
    if (!metadata) return null;
    try {
        const meta = JSON.parse(metadata) as { document_id?: unknown };
        return typeof meta.document_id === "string" ? meta.document_id : null;
    } catch {
        return null;
    }
}
