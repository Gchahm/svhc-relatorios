/**
 * Unit tests for the `/api/alerts` response shaping (feature 045 / TEST-003 / issue #70).
 *
 * Pins the response field set (no extra/missing keys) and order, and that mapping preserves values.
 * Imports the REAL `shapeAlertRow` (Node strips the `.ts` types).
 *
 * Run: `node --test "src/**\/*.test.mjs"`  (or `pnpm test:ts`)
 */
import test from "node:test";
import assert from "node:assert/strict";

import { shapeAlertRow, ALERT_RESPONSE_FIELDS } from "./shape.ts";

const row = {
    id: "a1",
    type: "duplicate_billing",
    severity: "critical",
    title: "T",
    description: "d",
    referencePeriod: "2025-12",
    resolved: false,
    resolvedAt: null,
    notes: null,
    metadata: '{"entry_ids":["e1"]}',
    // an extra column the query might carry that must NOT leak into the response:
    internalOnly: "secret",
};

test("shaped row exposes exactly the documented field set (FR-007)", () => {
    const out = shapeAlertRow(row);
    assert.deepEqual(Object.keys(out).sort(), [...ALERT_RESPONSE_FIELDS].sort());
    assert.ok(!("internalOnly" in out), "must not leak non-projected columns");
});

test("values are preserved verbatim", () => {
    const out = shapeAlertRow(row);
    for (const k of ALERT_RESPONSE_FIELDS) {
        assert.equal(out[k], row[k]);
    }
});

test("mapping an array preserves order", () => {
    const rows = [
        { ...row, id: "a1" },
        { ...row, id: "a2" },
        { ...row, id: "a3" },
    ];
    assert.deepEqual(
        rows.map(shapeAlertRow).map(r => r.id),
        ["a1", "a2", "a3"]
    );
});
