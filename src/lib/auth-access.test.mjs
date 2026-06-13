/**
 * Unit tests for the shared API-route auth decision (feature 045 / TEST-003 / issue #70).
 *
 * Pins deny-by-default: a missing session, a missing user, a missing role, or a role outside
 * ALLOWED_ROLES all deny; every allowed role allows. Also pins the UNAUTHORIZED_STATUS constant the
 * routes return. Imports the REAL `isAuthorized` (Node strips the `.ts` types).
 *
 * Run: `node --test "src/**\/*.test.mjs"`  (or `pnpm test:ts`)
 */
import test from "node:test";
import assert from "node:assert/strict";

import { isAuthorized, ALLOWED_ROLES, UNAUTHORIZED_STATUS } from "./auth-access.ts";

test("denies a null / undefined session (FR-007)", () => {
    assert.equal(isAuthorized(null), false);
    assert.equal(isAuthorized(undefined), false);
});

test("denies a session with no user / no role / null role", () => {
    assert.equal(isAuthorized({}), false);
    assert.equal(isAuthorized({ user: undefined }), false);
    assert.equal(isAuthorized({ user: {} }), false);
    assert.equal(isAuthorized({ user: { role: null } }), false);
    assert.equal(isAuthorized({ user: { role: "" } }), false);
});

test("denies a role outside ALLOWED_ROLES", () => {
    assert.equal(isAuthorized({ user: { role: "guest" } }), false);
    assert.equal(isAuthorized({ user: { role: "Admin" } }), false, "case-sensitive");
});

test("allows every role in ALLOWED_ROLES", () => {
    assert.ok(ALLOWED_ROLES.length > 0);
    for (const role of ALLOWED_ROLES) {
        assert.equal(isAuthorized({ user: { role } }), true, `${role} should be allowed`);
    }
});

test("UNAUTHORIZED_STATUS is the 4xx the routes return", () => {
    assert.equal(UNAUTHORIZED_STATUS, 403);
});

test("never throws for odd inputs (total)", () => {
    for (const s of [null, undefined, {}, { user: null }, { user: { role: 42 } }]) {
        assert.doesNotThrow(() => isAuthorized(s));
        assert.equal(typeof isAuthorized(s), "boolean");
    }
});
