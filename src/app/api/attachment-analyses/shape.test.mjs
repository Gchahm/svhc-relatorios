/**
 * Unit tests for the `/api/attachment-analyses` route helpers (feature 045 / TEST-003 / issue #70).
 *
 * Pins the optional period-scoping decision (param present ⇒ scoped, absent/empty ⇒ unscoped) and
 * the response projection field set. Imports the REAL helpers (Node strips the `.ts` types).
 *
 * Run: `node --test "src/**\/*.test.mjs"`  (or `pnpm test:ts`)
 */
import test from "node:test";
import assert from "node:assert/strict";

import { attachmentAnalysesPeriodScoped, ATTACHMENT_ANALYSIS_RESPONSE_FIELDS } from "./shape.ts";

test("period present (non-empty) ⇒ scoped", () => {
    assert.equal(attachmentAnalysesPeriodScoped("2025-12"), true);
});

test("period absent / empty ⇒ unscoped (FR-007)", () => {
    assert.equal(attachmentAnalysesPeriodScoped(null), false);
    assert.equal(attachmentAnalysesPeriodScoped(undefined), false);
    assert.equal(attachmentAnalysesPeriodScoped(""), false);
});

test("response projection lists the expected columns", () => {
    // A representative subset that consumers (EntriesClient, dialog) depend on.
    for (const field of ["id", "attachmentId", "amountMatch", "entryId", "vendorName", "error"]) {
        assert.ok(ATTACHMENT_ANALYSIS_RESPONSE_FIELDS.includes(field), `missing ${field}`);
    }
    assert.equal(new Set(ATTACHMENT_ANALYSIS_RESPONSE_FIELDS).size, ATTACHMENT_ANALYSIS_RESPONSE_FIELDS.length);
});
