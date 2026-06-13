/**
 * Unit tests for the entries deep-link → view-state decision (feature 045 / TEST-003 / issue #70).
 *
 * Pins the outcome→action mapping the entries client applies for the highest-risk interactive
 * flow: present+analysis → highlight + dialog; present, no analysis → highlight, no dialog; absent
 * → not-found notice, no dialog; invalid id → invalid notice, no lookup; filtered-but-present →
 * filter recovery; param period differing → selectPeriod. The notice text is asserted from the
 * catalog (FR-009). Imports the REAL `deepLinkView` (built on the REAL `resolveDeepLink`).
 *
 * Run: `node --test "src/**\/*.test.mjs"`  (or `pnpm test:ts`)
 */
import test from "node:test";
import assert from "node:assert/strict";

import { deepLinkView } from "./deeplinkView.ts";
import { catalog } from "../../../lib/i18n/catalog.ts";

const UUID = "3f1a2b3c-4d5e-6f70-8901-23456789abcd";

function base(overrides) {
    return {
        entryId: UUID,
        paramPeriod: "2025-12",
        selectedPeriod: "2025-12",
        hasActiveFilter: false,
        presentUnfiltered: true,
        filteredIndex: 7,
        hasAnalysis: true,
        ...overrides,
    };
}

test("present + analysis → highlight + open dialog, no notice, consumed", () => {
    const v = deepLinkView(base());
    assert.equal(v.highlightIndex, 7);
    assert.equal(v.openDialog, true);
    assert.equal(v.notice, undefined);
    assert.equal(v.consumed, true);
    assert.equal(v.clearFilters, undefined);
});

test("present, no analysis → highlight, NO dialog, no notice", () => {
    const v = deepLinkView(base({ hasAnalysis: false }));
    assert.equal(v.highlightIndex, 7);
    assert.equal(v.openDialog, false);
    assert.equal(v.notice, undefined);
    assert.equal(v.consumed, true);
});

test("absent entry → not-found notice, no dialog, no highlight, consumed", () => {
    const v = deepLinkView(base({ presentUnfiltered: false, filteredIndex: -1 }));
    assert.equal(v.highlightIndex, undefined);
    assert.equal(v.openDialog, false);
    assert.deepEqual(v.notice, { kind: "not-found" });
    assert.equal(v.consumed, true);
    // The notice text the client renders for this kind exists in the catalog (FR-009).
    assert.ok(catalog["pt-BR"].notice.deeplink_not_found_prefix.length > 0);
    assert.ok(catalog["pt-BR"].notice.deeplink_not_found_suffix.length > 0);
});

test("invalid id → invalid notice, no lookup/highlight/dialog, consumed", () => {
    const v = deepLinkView(base({ entryId: "not-a-uuid" }));
    assert.equal(v.highlightIndex, undefined);
    assert.equal(v.openDialog, false);
    assert.deepEqual(v.notice, { kind: "invalid" });
    assert.equal(v.consumed, true);
    assert.ok(catalog["pt-BR"].notice.deeplink_invalid.length > 0);
});

test("present but filtered out (active filter) → filter recovery, NOT consumed", () => {
    const v = deepLinkView(base({ hasActiveFilter: true, presentUnfiltered: true, filteredIndex: -1 }));
    assert.equal(v.clearFilters, true);
    assert.equal(v.openDialog, false);
    assert.equal(v.consumed, false);
    assert.equal(v.notice, undefined);
    assert.equal(v.highlightIndex, undefined);
});

test("param period differs from selected → selectPeriod set", () => {
    const v = deepLinkView(base({ paramPeriod: "2025-11", selectedPeriod: "2025-12" }));
    assert.equal(v.selectPeriod, "2025-11");
});

test("param period matches selected → no selectPeriod", () => {
    const v = deepLinkView(base());
    assert.equal(v.selectPeriod, undefined);
});
