/**
 * Pure mapping from a document reconciliation status to its i18n catalog label key (feature 045 /
 * TEST-003). The over/within/under/unknown badge text is a localized catalog string; this isolates
 * the status → catalog-key mapping so it is unit-testable against the catalog (the status *math*
 * stays in `documents.ts`, already pinned by the cross-language reconciliation contract).
 */

import type { DocumentStatus } from "./documents";
import type { DeepCatalogKey } from "./i18n/catalog";

/** The `status.*` catalog key whose localized value is the badge label for `status`. */
export function documentStatusLabelKey(status: DocumentStatus): DeepCatalogKey {
    return `status.${status}` as DeepCatalogKey;
}
