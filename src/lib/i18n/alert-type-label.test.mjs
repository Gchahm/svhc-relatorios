/**
 * Unit tests for the locale-aware alert type label (feature 045 / TEST-003 / issue #70).
 *
 * Pins that every curated alert type renders its pt-BR catalog label, an unknown type degrades to
 * a no-underscore humanized fallback (never raw snake_case — feature 038 / IMP-010), and the
 * function is total. Expected labels are read from the catalog (FR-009), never hardcoded English.
 *
 * Run: `node --test "src/**\/*.test.mjs"`  (or `pnpm test:ts`)
 */
import test from "node:test";
import assert from "node:assert/strict";

import { alertTypeLabelFor } from "./alert-type-label.ts";
import { catalog } from "./catalog.ts";

test("every catalog alert type → its pt-BR catalog label (FR-004/FR-009)", () => {
    const types = catalog["pt-BR"].alert.types;
    const keys = Object.keys(types);
    assert.ok(keys.length > 0, "catalog must define alert types");
    for (const type of keys) {
        assert.equal(alertTypeLabelFor(type, "pt-BR"), types[type]);
    }
});

test("unknown type → humanized fallback with no underscores (FR-004)", () => {
    const out = alertTypeLabelFor("some_future_check", "pt-BR");
    assert.equal(out, "Some future check");
    assert.ok(!out.includes("_"), "fallback must not contain underscores");
});

test("empty string → empty string", () => {
    assert.equal(alertTypeLabelFor("", "pt-BR"), "");
});

test("never returns raw snake_case and never throws (total)", () => {
    for (const input of ["", "x", "a_b_c", "ALREADY_UPPER", "123_456", "ünïcödé_tëst"]) {
        assert.doesNotThrow(() => alertTypeLabelFor(input, "pt-BR"));
        const out = alertTypeLabelFor(input, "pt-BR");
        assert.equal(typeof out, "string");
        if (input.length > 0) assert.ok(!out.includes("_"), `"${input}" leaked an underscore`);
    }
});

test("resolves per requested locale (en fallback path)", () => {
    const enTypes = catalog["en"].alert.types;
    const someType = Object.keys(enTypes)[0];
    assert.equal(alertTypeLabelFor(someType, "en"), enTypes[someType]);
});
