/**
 * Pure row→response shaping for `GET /api/documents` (feature 045 / TEST-003).
 *
 * The route's only post-query logic is deriving the over/within/under/unknown `status` from the
 * link aggregates via the shared tolerance contract (`@/lib/documents`). Extracted here so that
 * derivation is unit-testable without the Cloudflare runtime; the route owns the Drizzle query.
 *
 * `shapeDocumentRow` is generic over the concrete (Drizzle-inferred) row so it pins the *status
 * derivation* (and that all input fields are preserved) without coupling to Drizzle column types —
 * it only requires the two aggregates the status math reads.
 */

// Relative + explicit `.ts` so this pure module is importable under `node:test` (no path-alias
// resolution, and Node needs the extension); `moduleResolution: "bundler"` accepts the extension
// for tsc and Next (feature 045 / TEST-003). `../../../` reaches src/app/api/documents → src/.
import { documentStatus, type DocumentStatus } from "../../../lib/documents.ts";

/** The minimal shape the status derivation reads off a document list row. */
export interface DocumentStatusInput {
    totalValue: number | null;
    sumEntries: number;
}

/** Add the reconciliation `status` (shared tolerance contract) to a document list row. */
export function shapeDocumentRow<T extends DocumentStatusInput>(row: T): T & { status: DocumentStatus } {
    return { ...row, status: documentStatus(row.sumEntries, row.totalValue) };
}
