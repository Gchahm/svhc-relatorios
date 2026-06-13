/**
 * Unit tests for the alerts metadata helpers (feature 045 / TEST-003 / issue #70).
 *
 * Pins the affected-entry derivation (single `entry_id` vs `entry_ids[]`, mixed/malformed/null),
 * the deep-link URL shape, and the referenced-document id — the auditing-evidence routing the
 * alerts surface relies on. Imports the REAL helpers (Node >= 22.18 strips the `.ts` types).
 *
 * Run: `node --test "src/**\/*.test.mjs"`  (or `pnpm test:ts`)
 */
import test from "node:test";
import assert from "node:assert/strict";

import { affectedEntryIds, entryHref, referencedDocumentId } from "./alerts-helpers.ts";

const UUID = "3f1a2b3c-4d5e-6f70-8901-23456789abcd";

test("affectedEntryIds: single entry_id → one-element list (FR-003)", () => {
    assert.deepEqual(affectedEntryIds(`{"entry_id":"${UUID}"}`), [UUID]);
});

test("affectedEntryIds: entry_ids array is honored (FR-003)", () => {
    assert.deepEqual(affectedEntryIds('{"entry_ids":["a","b"]}'), ["a", "b"]);
});

test("affectedEntryIds: array form wins over a stray entry_id", () => {
    assert.deepEqual(affectedEntryIds('{"entry_ids":["a"],"entry_id":"z"}'), ["a"]);
});

test("affectedEntryIds: non-string array members are dropped", () => {
    assert.deepEqual(affectedEntryIds('{"entry_ids":["a",1,null,true,"b"]}'), ["a", "b"]);
});

test("affectedEntryIds: malformed / null / empty metadata → [] and never throws (FR-003)", () => {
    for (const bad of [null, "", "{ not json", "[1,2,3]", "42", '{"other":1}', "{}"]) {
        assert.doesNotThrow(() => affectedEntryIds(bad));
        assert.deepEqual(affectedEntryIds(bad), []);
    }
});

test("entryHref: deep-link URL shape the entries surface consumes (FR-003)", () => {
    assert.equal(entryHref("2025-12", UUID), `/dashboard/entries?period=2025-12&entry=${UUID}`);
});

test("entryHref: both params are URL-encoded", () => {
    assert.equal(entryHref("2025/12", "a b"), "/dashboard/entries?period=2025%2F12&entry=a%20b");
});

test("referencedDocumentId: string document_id, else null; never throws", () => {
    assert.equal(referencedDocumentId('{"document_id":"d1"}'), "d1");
    for (const none of [null, "", "{ not json", '{"document_id":42}', "{}"]) {
        assert.doesNotThrow(() => referencedDocumentId(none));
        assert.equal(referencedDocumentId(none), null);
    }
});
