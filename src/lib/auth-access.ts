/**
 * Shared API-route authorization decision (feature 045 / TEST-003).
 *
 * The list/detail API routes all gate on the same rule: an authenticated session whose user has an
 * allowed role. That rule was copy-pasted (and untested) across every route. This module is the
 * single, pure, testable source of truth for it — extracted from the Cloudflare/better-auth
 * plumbing so it can be unit-tested with `node:test` without standing up the Workers runtime.
 *
 * The route still owns `initAuth()` / `getDb()` / the DB query; it imports these and calls
 * `isAuthorized(session)`, returning `UNAUTHORIZED_STATUS` when the decision is deny.
 */

/** Roles permitted to read fiscal data through the dashboard API. */
export const ALLOWED_ROLES: readonly string[] = ["admin", "member"];

/** HTTP status the routes return when the auth decision is deny. */
export const UNAUTHORIZED_STATUS = 403;

/**
 * Minimal session shape the decision needs — deliberately structural so the pure function takes no
 * dependency on better-auth's concrete session type (and tests can pass plain objects).
 */
export type SessionLike = { user?: { role?: string | null } | null } | null | undefined;

/**
 * Allow iff there is a session AND its user's role is one of {@link ALLOWED_ROLES}. Pure and total:
 * a null/undefined session, a missing user, or a missing/disallowed role all deny. Never throws.
 */
export function isAuthorized(session: SessionLike): boolean {
    const role = session?.user?.role;
    return typeof role === "string" && ALLOWED_ROLES.includes(role);
}
