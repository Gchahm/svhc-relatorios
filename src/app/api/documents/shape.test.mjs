/**
 * Unit tests for the `/api/documents` response shaping (feature 045 / TEST-003 / issue #70).
 *
 * Pins that the route adds the over/within/under/unknown `status` per the shared tolerance contract
 * and preserves all input fields. The status *math* is also independently pinned by the
 * cross-language reconciliation contract in `src/lib/documents.test.mjs`. Imports the REAL
 * `shapeDocumentRow` (Node strips the `.ts` types).
 *
 * Run: `node --test "src/**\/*.test.mjs"`  (or `pnpm test:ts`)
 */
import test from "node:test";
import assert from "node:assert/strict";

import { shapeDocumentRow } from "./shape.ts";

function row(overrides) {
    return {
        id: "d1",
        documentNumber: "123",
        issuerCnpj: "12345678000199",
        issuerName: "ACME",
        documentType: "nfse",
        totalValue: 100,
        linkedCount: 1,
        sumEntries: 100,
        ...overrides,
    };
}

test("derives status via the shared tolerance contract (FR-007)", () => {
    assert.equal(shapeDocumentRow(row({ sumEntries: 100, totalValue: 100 })).status, "within");
    assert.equal(shapeDocumentRow(row({ sumEntries: 100.03, totalValue: 100 })).status, "within"); // ≤ R$0.05
    assert.equal(shapeDocumentRow(row({ sumEntries: 200, totalValue: 100 })).status, "over");
    assert.equal(shapeDocumentRow(row({ sumEntries: 50, totalValue: 100 })).status, "under");
    assert.equal(shapeDocumentRow(row({ sumEntries: 0, totalValue: null })).status, "unknown");
    assert.equal(shapeDocumentRow(row({ sumEntries: 10, totalValue: 0 })).status, "unknown");
});

test("preserves all input fields and adds only status", () => {
    const input = row();
    const out = shapeDocumentRow(input);
    for (const k of Object.keys(input)) assert.equal(out[k], input[k]);
    assert.ok("status" in out);
    assert.deepEqual(Object.keys(out).sort(), [...Object.keys(input), "status"].sort());
});
