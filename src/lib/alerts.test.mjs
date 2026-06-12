/**
 * Unit test for the shared alert type → label map (IMP-010 / issue #47).
 *
 * Pins the `alertTypeLabel` contract from specs/038-alert-type-labels/contracts/alerts.md:
 * curated lookup, the snake_case → Sentence case fallback for unknown types, the empty-string
 * identity, a single non-snake word, and the never-throws (total) guarantee.
 *
 * Runs on the Node.js built-in test runner (no new dependency): Node >= 22.18 strips the
 * TypeScript types from `alerts.ts` natively, so this imports the REAL implementation.
 *
 * Run: `node --test "src/**\/*.test.mjs"`  (or `pnpm test`)
 */
import test from "node:test";
import assert from "node:assert/strict";
import { alertTypeLabel, ALERT_TYPE_LABELS } from "./alerts.ts";

test("every curated type maps to its curated label (FR-002)", () => {
    for (const [type, label] of Object.entries(ALERT_TYPE_LABELS)) {
        assert.equal(alertTypeLabel(type), label);
    }
    // Spot-check a couple of representative entries explicitly.
    assert.equal(alertTypeLabel("document_overpayment"), "Document overpayment");
    assert.equal(alertTypeLabel("large_expense_no_attachment"), "Large expense without attachment");
});

test("unknown snake_case type falls back to Sentence case with no underscores (FR-003)", () => {
    const out = alertTypeLabel("some_new_check");
    assert.equal(out, "Some new check");
    assert.ok(!out.includes("_"), "fallback must not contain underscores");
});

test("empty string returns empty string (edge case)", () => {
    assert.equal(alertTypeLabel(""), "");
});

test("single non-snake word is capitalized", () => {
    assert.equal(alertTypeLabel("orphan"), "Orphan");
});

test("an already-spaced value is returned readably, never raw lowercase", () => {
    assert.equal(alertTypeLabel("already spaced value"), "Already spaced value");
});

test("never throws for any string input (FR-007)", () => {
    for (const input of ["", "x", "a_b_c", "ALREADY_UPPER", "  ", "123_456", "ünïcödé_tëst"]) {
        assert.doesNotThrow(() => alertTypeLabel(input));
        assert.equal(typeof alertTypeLabel(input), "string");
    }
});
