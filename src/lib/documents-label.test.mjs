/**
 * Unit tests for the document status → catalog label-key mapping (feature 045 / TEST-003 / #70).
 *
 * Pins that each over/within/under/unknown status maps to the `status.*` catalog key whose pt-BR
 * value is the rendered badge label. Expected labels are read from the catalog (FR-009), never
 * hardcoded English. The status *math* is pinned separately by the cross-language reconciliation
 * contract in `documents.test.mjs` (retained, not duplicated here).
 *
 * Run: `node --test "src/**\/*.test.mjs"`  (or `pnpm test:ts`)
 */
import test from "node:test";
import assert from "node:assert/strict";

import { documentStatusLabelKey } from "./documents-label.ts";
import { catalog } from "./i18n/catalog.ts";

const STATUSES = ["over", "within", "under", "unknown"];

test("each status maps to its status.* catalog key", () => {
    for (const status of STATUSES) {
        assert.equal(documentStatusLabelKey(status), `status.${status}`);
    }
});

test("the key resolves to a non-empty pt-BR catalog label (FR-005/FR-009)", () => {
    for (const status of STATUSES) {
        const key = documentStatusLabelKey(status);
        // key is "status.<status>" — resolve it against the catalog the UI uses.
        const [section, leaf] = key.split(".");
        const label = catalog["pt-BR"][section][leaf];
        assert.equal(label, catalog["pt-BR"].status[status]);
        assert.ok(typeof label === "string" && label.length > 0, `${status} has no pt-BR label`);
    }
});
