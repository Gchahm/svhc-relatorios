/**
 * Unit tests for the entries deep-link resolution helpers (feature 037 / issue #45 / IMP-008).
 *
 * Pins `isValidEntryId`, `shortenEntryId`, and the `resolveDeepLink` decision table from
 * specs/037-deeplink-not-found-notice/contracts/deepLink.md. Runs on the Node.js built-in
 * test runner (no new dependency): Node >= 22.18 strips the TypeScript types from `deepLink.ts`
 * natively, so this imports the REAL helpers (never a re-derived copy).
 *
 * Run: `node --test "src/**\/*.test.mjs"`  (or `pnpm test`)
 */
import test from "node:test";
import assert from "node:assert/strict";

import { isValidEntryId, shortenEntryId, resolveDeepLink } from "./deepLink.ts";

const UUID = "3f1a2b3c-4d5e-6f70-8901-23456789abcd";

test("isValidEntryId accepts canonical UUID shape (case-insensitive)", () => {
    assert.equal(isValidEntryId(UUID), true);
    assert.equal(isValidEntryId(UUID.toUpperCase()), true);
});

test("isValidEntryId rejects non-UUID values", () => {
    assert.equal(isValidEntryId(""), false);
    assert.equal(isValidEntryId("not-a-uuid"), false);
    assert.equal(isValidEntryId("3f1a2b3c4d5e6f70890123456789abcd"), false, "no dashes");
    assert.equal(isValidEntryId("3f1a2b3c-4d5e-6f70-8901-23456789abc"), false, "too short");
    assert.equal(isValidEntryId(` ${UUID} `), false, "surrounding whitespace");
});

test("shortenEntryId truncates long ids and passes short ones through", () => {
    assert.equal(shortenEntryId(UUID), "3f1a2b3c…");
    assert.equal(shortenEntryId("abc"), "abc");
    assert.equal(shortenEntryId(""), "");
});

test("resolveDeepLink: invalid id short-circuits before any lookup", () => {
    const r = resolveDeepLink({
        entryId: "junk",
        hasActiveFilter: true,
        presentUnfiltered: true,
        filteredIndex: 5,
    });
    assert.deepEqual(r, { outcome: "invalid" });
});

test("resolveDeepLink: visible row is found even with an active filter", () => {
    const r = resolveDeepLink({
        entryId: UUID,
        hasActiveFilter: true,
        presentUnfiltered: true,
        filteredIndex: 5,
    });
    assert.deepEqual(r, { outcome: "found", index: 5 });
});

test("resolveDeepLink: recovery requires present-unfiltered AND an active filter", () => {
    assert.deepEqual(
        resolveDeepLink({ entryId: UUID, hasActiveFilter: true, presentUnfiltered: true, filteredIndex: -1 }),
        { outcome: "recovered-from-filter" }
    );
    // present but no filter active => genuinely not in the filtered list for another reason: not-found
    assert.deepEqual(
        resolveDeepLink({ entryId: UUID, hasActiveFilter: false, presentUnfiltered: true, filteredIndex: -1 }),
        { outcome: "not-found" }
    );
});

test("resolveDeepLink: absent entry is not-found regardless of stray filters (FR-005)", () => {
    assert.deepEqual(
        resolveDeepLink({ entryId: UUID, hasActiveFilter: true, presentUnfiltered: false, filteredIndex: -1 }),
        { outcome: "not-found" }
    );
    assert.deepEqual(
        resolveDeepLink({ entryId: UUID, hasActiveFilter: false, presentUnfiltered: false, filteredIndex: -1 }),
        { outcome: "not-found" }
    );
});

test("resolveDeepLink: no recovery loop — once filters are cleared, recovery cannot re-fire", () => {
    // After clearing filters, hasActiveFilter is false; the row is now in `filtered`.
    const afterClear = resolveDeepLink({
        entryId: UUID,
        hasActiveFilter: false,
        presentUnfiltered: true,
        filteredIndex: 2,
    });
    assert.deepEqual(afterClear, { outcome: "found", index: 2 });
    // And if it somehow still weren't visible, it's not-found (terminal), never recovered again.
    const stillHidden = resolveDeepLink({
        entryId: UUID,
        hasActiveFilter: false,
        presentUnfiltered: true,
        filteredIndex: -1,
    });
    assert.deepEqual(stillHidden, { outcome: "not-found" });
});
