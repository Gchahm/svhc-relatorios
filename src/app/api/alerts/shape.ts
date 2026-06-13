/**
 * Pure row→response shaping for `GET /api/alerts` (feature 045 / TEST-003).
 *
 * Extracted from the route so the response contract (the exact projected field set) is unit-testable
 * without the Cloudflare runtime. The route owns the Drizzle query; it maps each row through this.
 *
 * `shapeAlertRow` is a structural identity projection: it picks exactly the documented keys, so it
 * is generic over the concrete (Drizzle-inferred) row type — pinning the *field set* the response
 * exposes without coupling the test to Drizzle's column value types.
 */

/** The exact key set the alerts list response exposes (in order). */
export const ALERT_RESPONSE_FIELDS = [
    "id",
    "type",
    "severity",
    "title",
    "description",
    "referencePeriod",
    "resolved",
    "resolvedAt",
    "notes",
    "metadata",
] as const;

type AlertResponseField = (typeof ALERT_RESPONSE_FIELDS)[number];

/** Project one alert row to its stable response shape (identity over {@link ALERT_RESPONSE_FIELDS}). */
export function shapeAlertRow<T extends Record<AlertResponseField, unknown>>(row: T): Pick<T, AlertResponseField> {
    return {
        id: row.id,
        type: row.type,
        severity: row.severity,
        title: row.title,
        description: row.description,
        referencePeriod: row.referencePeriod,
        resolved: row.resolved,
        resolvedAt: row.resolvedAt,
        notes: row.notes,
        metadata: row.metadata,
    } as Pick<T, AlertResponseField>;
}
