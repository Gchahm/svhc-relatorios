// Pure helpers for the entries deep-link (`?period=<YYYY-MM>&entry=<id>`) resolution.
//
// Extracted out of `EntriesClient` so the branching is unit-testable without React/DOM
// (mirrors `src/lib/documents.ts` + its `.test.mjs`). The component owns the React glue
// (state, effect, JSX); this module owns only the decision over the loaded data.
//
// Feature 037 (issue #45 / IMP-008): the deep-link effect used to do nothing when the entry
// wasn't in the visible list, so a stale/wrong/filtered/invalid link failed silently. The
// resolution below distinguishes the four outcomes so the effect can give explicit feedback.

// Canonical UUID shape, case-insensitive. Entry ids are persisted text UUIDs (feature 031),
// but they may be deterministic ids (`det_id(...)`) whose version/variant bits aren't strictly
// RFC-4122 compliant — so this validates SHAPE only, not the v4 version/variant nibbles, to
// avoid rejecting real ids.
const UUID_SHAPE = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

/** True iff `value` is a canonical UUID shape (the accepted entry-id form). */
export function isValidEntryId(value: string): boolean {
    return UUID_SHAPE.test(value);
}

/** Compact id for display in the notice: first 8 chars + ellipsis when longer (e.g. "3f1a2b3c…"). */
export function shortenEntryId(value: string): string {
    return value.length > 8 ? `${value.slice(0, 8)}…` : value;
}

export interface ResolveInput {
    /** The raw `entry` URL param (non-empty when the effect runs). */
    entryId: string;
    /** Whether any client-side filter (subcategory/search/docType/matchStatus) is active. */
    hasActiveFilter: boolean;
    /** Whether `entryId` exists in the period's UNFILTERED entries. */
    presentUnfiltered: boolean;
    /** Index of `entryId` in the FILTERED+sorted list, or -1 when absent. */
    filteredIndex: number;
}

export type DeepLinkResolution =
    | { outcome: "invalid" }
    | { outcome: "found"; index: number }
    | { outcome: "recovered-from-filter" }
    | { outcome: "not-found" };

/**
 * Decide how a deep-link resolves against the loaded data. Decision order is exact and matters:
 *
 *   1. invalid                — id fails UUID-shape validation (never look up junk)
 *   2. found                  — visible in the filtered list (even if a filter is active)
 *   3. recovered-from-filter  — absent from the filtered list but present unfiltered AND a
 *                               filter is active (clearing it will surface the row)
 *   4. not-found              — genuinely absent from the period's loaded data
 *
 * `recovered-from-filter` requires BOTH `presentUnfiltered` and `hasActiveFilter`, so an absent
 * entry with stray filters still resolves `not-found` (FR-005). Because recovery only fires when
 * a filter is active, clearing the filters makes a re-run land on `found` or `not-found` — no
 * recovery loop.
 */
export function resolveDeepLink(input: ResolveInput): DeepLinkResolution {
    if (!isValidEntryId(input.entryId)) {
        return { outcome: "invalid" };
    }
    if (input.filteredIndex >= 0) {
        return { outcome: "found", index: input.filteredIndex };
    }
    if (input.presentUnfiltered && input.hasActiveFilter) {
        return { outcome: "recovered-from-filter" };
    }
    return { outcome: "not-found" };
}
