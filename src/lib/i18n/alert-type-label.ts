/**
 * Pure, locale-aware alert type → human-readable label (feature 045 / TEST-003).
 *
 * Extracted from `useAlertTypeLabel` (in `client.tsx`, a `"use client"` `.tsx` that `node:test`
 * cannot import) so the labeling logic is unit-testable against the catalog. The hook now calls
 * this. Uses the catalog `alert.types.<type>` entry when present; otherwise a humanized
 * `snake_case → Sentence case` fallback. NEVER returns raw snake_case (FR-004). `""` → `""`. Total.
 */

import type { SupportedLocale } from "./catalog.ts";
import { catalog } from "./catalog.ts";

export function alertTypeLabelFor(type: string, locale: SupportedLocale): string {
    if (!type) return "";
    const types = catalog[locale].alert.types as Record<string, string>;
    const curated = types[type];
    if (typeof curated === "string" && curated.length > 0) return curated;
    const spaced = type.replace(/_/g, " ");
    return spaced.charAt(0).toUpperCase() + spaced.slice(1);
}
