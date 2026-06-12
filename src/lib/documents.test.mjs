/**
 * Cross-language reconciliation contract test — TypeScript side (IMP-006 / issue #43).
 *
 * The over/within/under reconciliation decision lives in two implementations, two
 * languages: `documentStatus` here in `src/lib/documents.ts` (drives the over/within/under
 * badge on /dashboard/documents) and `reconcile_group` in `scripts/analysis/nf_groups.py`
 * (drives `amount_match`, shared-NF reconciliation, and the `document_overpayment` alert).
 * They were identical but nothing bound them, so the first unilateral tweak would make the
 * badge and the alert that created it silently disagree.
 *
 * This test pins the TS side to the SINGLE shared fixture
 * `scripts/analysis/reconciliation_contract.json`; `scripts/tests/test_reconciliation_contract.py`
 * pins the Python side to the same file. A unilateral change to either side's tolerance
 * constants or comparison operators flips a fixture case and fails that side's test.
 *
 * Runs on the Node.js built-in test runner (no new dependency): Node >= 22.18 strips the
 * TypeScript types from `documents.ts` natively, so this imports the REAL `documentStatus`
 * (never a re-derived copy of the math).
 *
 * Run: `node --test "src/**\/*.test.mjs"`  (or `pnpm test`)
 */
import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, resolve } from "node:path";

import { documentStatus } from "./documents.ts";

const here = dirname(fileURLToPath(import.meta.url));
const fixturePath = resolve(here, "../../scripts/analysis/reconciliation_contract.json");
const { cases } = JSON.parse(readFileSync(fixturePath, "utf8"));

const VALID = new Set(["within", "over", "under", "unknown"]);

test("fixture is well-formed (FR-001)", () => {
    assert.ok(cases.length > 0, "fixture must contain at least one case");
    const names = new Set();
    for (const c of cases) {
        assert.ok("name" in c && "sum" in c && "total" in c, `${c.name}: missing field`);
        assert.ok(VALID.has(c.status), `${c.name}: invalid status ${c.status}`);
        assert.ok(!names.has(c.name), `duplicate case name ${c.name}`);
        names.add(c.name);
    }
});

test("documentStatus matches the shared contract (FR-004/FR-005)", () => {
    for (const c of cases) {
        const got = documentStatus(c.sum, c.total);
        assert.equal(
            got,
            c.status,
            `${c.name}: sum=${c.sum} total=${c.total} -> documentStatus=${got} but fixture expects ${c.status}`
        );
    }
});
