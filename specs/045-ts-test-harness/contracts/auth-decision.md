# Contract: auth decision — `src/lib/auth-access.ts`

```ts
export const ALLOWED_ROLES: readonly string[]; // ["admin", "member"]
export const UNAUTHORIZED_STATUS: number;       // 403
export type SessionLike = { user?: { role?: string | null } } | null | undefined;
export function isAuthorized(session: SessionLike): boolean;
```

`isAuthorized` ⇒ `true` iff `session` is truthy AND `session.user.role` is a string in
`ALLOWED_ROLES`; else `false`. Pure, total, no Cloudflare/better-auth import.

The three routes import `ALLOWED_ROLES`/`UNAUTHORIZED_STATUS` and gate with
`if (!isAuthorized(session)) return NextResponse.json({ error: "Unauthorized" }, { status: UNAUTHORIZED_STATUS })`.

## Pinned by `auth-access.test.mjs`
- `null` / `undefined` session → deny.
- session with no `user` / no `role` / `role: null` → deny.
- `role: "guest"` (not in `ALLOWED_ROLES`) → deny.
- `role: "admin"` and `role: "member"` → allow (loop over `ALLOWED_ROLES`).
- `UNAUTHORIZED_STATUS === 403` (asserted as the exported constant, not an inline literal in
  the route — the route references the constant).
