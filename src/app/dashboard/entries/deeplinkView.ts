/**
 * Pure deep-link → view-state decision for the entries surface (feature 045 / TEST-003).
 *
 * The entries client reads `?period=`/`?entry=`, then (once the period's data has loaded) resolves
 * the target row and acts: select the period, scroll/highlight the row, auto-open the analysis
 * dialog when an analysis exists, recover from an active filter, or surface the feature-037
 * not-found/invalid notice. That outcome→action mapping was inline in `EntriesClient` and untested.
 *
 * This isolates the mapping as a pure function built on the existing `resolveDeepLink` core
 * (unchanged), so the highest-risk interactive flow is unit-tested without a DOM. `EntriesClient`
 * consumes it, so the test exercises the real production decision. The notice carries the same
 * `kind` the client renders (`catalog.notice.deeplink_*`), not pre-localized text.
 */

import { resolveDeepLink } from "./deepLink.ts";

export interface DeepLinkViewInput {
    /** The raw `?entry=` param. */
    entryId: string;
    /** The raw `?period=` param (or null when absent). */
    paramPeriod: string | null;
    /** The period currently selected in the client. */
    selectedPeriod: string | null;
    /** Whether any list filter is active (subcategory/search/doc-type/match-status). */
    hasActiveFilter: boolean;
    /** Whether the entry is present in the unfiltered set for the loaded period. */
    presentUnfiltered: boolean;
    /** The entry's index in the filtered list, or -1 when not visible. */
    filteredIndex: number;
    /** Whether an attachment analysis exists for the entry (drives dialog auto-open). */
    hasAnalysis: boolean;
}

export interface DeepLinkView {
    /** Set when the param period differs from the selected period — select it first. */
    selectPeriod?: string;
    /** Row index to scroll to + highlight (the "found" terminal outcome). */
    highlightIndex?: number;
    /** Auto-open the analysis dialog (only when found AND an analysis exists). */
    openDialog: boolean;
    /** Transitional: clear all filters and let the effect re-run to land on the now-visible row. */
    clearFilters?: boolean;
    /** Non-blocking feature-037 notice to show (terminal not-found / invalid), else undefined. */
    notice?: { kind: "not-found" | "invalid" };
    /** Whether this outcome consumes the deep link (terminal) and strips the URL params. */
    consumed: boolean;
}

/**
 * Map a deep-link resolution to the view-state the client applies. Pure; mirrors the
 * `EntriesClient` effect exactly. The caller is responsible for the period-load gate (only call
 * once the loaded data is for `paramPeriod`); this function still surfaces `selectPeriod` so the
 * client selects the right period before acting.
 */
export function deepLinkView(input: DeepLinkViewInput): DeepLinkView {
    const selectPeriod =
        input.paramPeriod && input.paramPeriod !== input.selectedPeriod ? input.paramPeriod : undefined;

    const resolution = resolveDeepLink({
        entryId: input.entryId,
        hasActiveFilter: input.hasActiveFilter,
        presentUnfiltered: input.presentUnfiltered,
        filteredIndex: input.filteredIndex,
    });

    // Filter recovery is transitional: clear filters, re-run, do NOT consume the link.
    if (resolution.outcome === "recovered-from-filter") {
        return { selectPeriod, openDialog: false, clearFilters: true, consumed: false };
    }

    // Terminal: found → scroll/highlight (+ dialog when an analysis exists); else a notice.
    if (resolution.outcome === "found") {
        return {
            selectPeriod,
            highlightIndex: resolution.index,
            openDialog: input.hasAnalysis,
            consumed: true,
        };
    }

    // "not-found" or "invalid" — surface a non-blocking notice instead of failing silently.
    return { selectPeriod, openDialog: false, notice: { kind: resolution.outcome }, consumed: true };
}
