/**
 * Unit tests for i18n message catalog completeness
 * Ensures pt-BR is complete and en is consistent
 *
 * Run with: npm test or pnpm test
 */

import { test } from "node:test";
import assert from "node:assert";
import { catalog } from "../../src/lib/i18n/catalog.ts";

/**
 * Recursively extract all keys from a nested object
 */
function getAllKeys(obj, prefix = "") {
    const keys = [];
    for (const [key, value] of Object.entries(obj)) {
        const newKey = prefix ? `${prefix}.${key}` : key;
        if (typeof value === "object" && value !== null && !Array.isArray(value)) {
            keys.push(...getAllKeys(value, newKey));
        } else {
            keys.push(newKey);
        }
    }
    return keys;
}

/**
 * Recursively check that all keys exist in a target object
 */
function checkKeysExist(sourceObj, targetObj, prefix = "", missingKeys = []) {
    for (const [key, value] of Object.entries(sourceObj)) {
        const newKey = prefix ? `${prefix}.${key}` : key;
        if (typeof value === "object" && value !== null && !Array.isArray(value)) {
            if (typeof targetObj[key] !== "object" || targetObj[key] === null) {
                missingKeys.push(newKey);
            } else {
                checkKeysExist(value, targetObj[key], newKey, missingKeys);
            }
        } else {
            if (!(key in targetObj)) {
                missingKeys.push(newKey);
            }
        }
    }
    return missingKeys;
}

test("Catalog: pt-BR has all required keys", async t => {
    const ptBr = catalog["pt-BR"];
    assert.ok(ptBr, "pt-BR locale should exist in catalog");
    assert.ok(Object.keys(ptBr).length > 0, "pt-BR should have at least one section");

    const sections = [
        "nav",
        "button",
        "page",
        "dialog",
        "table",
        "form",
        "badge",
        "alert",
        "error",
        "common",
        "auth",
        "formatting",
    ];
    for (const section of sections) {
        assert.ok(section in ptBr, `pt-BR should have "${section}" section`);
        assert.ok(typeof ptBr[section] === "object", `pt-BR.${section} should be an object`);
    }
});

test("Catalog: pt-BR has no empty string values", async t => {
    const ptBr = catalog["pt-BR"];
    const keys = getAllKeys(ptBr);
    const emptyKeys = [];

    for (const key of keys) {
        const parts = key.split(".");
        let value = ptBr;
        for (const part of parts) {
            value = value[part];
        }
        if (value === "") {
            emptyKeys.push(key);
        }
    }

    assert.equal(emptyKeys.length, 0, `pt-BR should have no empty string values. Found: ${emptyKeys.join(", ")}`);
});

test("Catalog: en keys are a subset of pt-BR (no orphan keys)", async t => {
    const ptBr = catalog["pt-BR"];
    const en = catalog.en;

    const missingKeys = checkKeysExist(en, ptBr);
    assert.equal(
        missingKeys.length,
        0,
        `en should only have keys that exist in pt-BR. Orphan keys: ${missingKeys.join(", ")}`
    );
});

test("Catalog: all alert.types keys are consistent", async t => {
    const ptBr = catalog["pt-BR"].alert.types;
    const en = catalog.en.alert.types;

    const ptBrKeys = Object.keys(ptBr).sort();
    const enKeys = Object.keys(en).sort();

    // en keys should be a subset of ptBr keys
    for (const key of enKeys) {
        assert.ok(key in ptBr, `Alert type "${key}" exists in en but not in pt-BR`);
    }
});

test("Catalog: no undefined values", async t => {
    const locales = ["pt-BR", "en"];

    for (const locale of locales) {
        const catalog_locale = catalog[locale];
        const keys = getAllKeys(catalog_locale);

        for (const key of keys) {
            const parts = key.split(".");
            let value = catalog_locale;
            for (const part of parts) {
                value = value[part];
            }

            assert.notEqual(value, undefined, `Catalog key "${key}" in locale "${locale}" should not be undefined`);
            assert.notEqual(value, null, `Catalog key "${key}" in locale "${locale}" should not be null`);
        }
    }
});

test("Catalog: all values are strings", async t => {
    const locales = ["pt-BR", "en"];

    for (const locale of locales) {
        const catalog_locale = catalog[locale];
        const keys = getAllKeys(catalog_locale);

        for (const key of keys) {
            const parts = key.split(".");
            let value = catalog_locale;
            for (const part of parts) {
                value = value[part];
            }

            assert.equal(
                typeof value,
                "string",
                `Catalog key "${key}" in locale "${locale}" should be a string, got ${typeof value}`
            );
        }
    }
});

test("Catalog: pt-BR has complete section structure", async t => {
    const ptBr = catalog["pt-BR"];

    // Expected sections
    const expectedSections = {
        nav: ["home", "entries", "documents", "alerts", "dashboard", "settings"],
        button: ["submit", "cancel", "save", "delete", "close", "search", "download", "upload"],
        page: [
            "entries_title",
            "entries_description",
            "documents_title",
            "documents_description",
            "alerts_title",
            "alerts_description",
        ],
        table: ["period", "date", "amount", "vendor", "description", "attachment", "actions", "status", "type"],
        badge: ["pending", "classified", "analyzed", "error", "success", "warning", "info"],
        alert: {
            types: [
                "attachment_amount_mismatch",
                "attachment_vendor_mismatch",
                "attachment_date_mismatch",
                "attachment_page_error",
                "duplicate_billing",
                "duplicate_entry",
                "negative_credit",
                "large_expense_no_attachment",
                "document_overpayment",
                "scrape_inconsistency",
                "portal_row_vanished",
            ],
        },
        error: ["not_found", "unauthorized", "server_error", "network_error", "loading_failed"],
        common: ["loading", "no_data", "error", "success", "confirm", "yes", "no"],
        auth: [
            "sign_in_title",
            "sign_in_description",
            "email_label",
            "password_label",
            "sign_in_button",
            "sign_in_error",
            "invalid_credentials",
            "session_expired",
            "sign_out",
        ],
        formatting: ["currency", "date", "percent"],
    };

    for (const [section, expectedKeys] of Object.entries(expectedSections)) {
        if (section === "alert") {
            for (const [subsection, subKeys] of Object.entries(expectedKeys)) {
                for (const key of subKeys) {
                    assert.ok(key in ptBr[section][subsection], `pt-BR.${section}.${subsection}.${key} should exist`);
                }
            }
        } else if (Array.isArray(expectedKeys)) {
            for (const key of expectedKeys) {
                assert.ok(key in ptBr[section], `pt-BR.${section}.${key} should exist`);
            }
        }
    }
});
