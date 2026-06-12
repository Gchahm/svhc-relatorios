/**
 * Unit tests for i18n message catalog completeness
 * Ensures pt-BR is complete and en is consistent
 *
 * Run with: npm test or pnpm test
 */

import { test } from "node:test";
import assert from "node:assert";
import { catalog } from "./catalog.ts";

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

test("Catalog: pt-BR has all required keys", async () => {
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
        "app",
        "access",
        "formatting",
    ];
    for (const section of sections) {
        assert.ok(section in ptBr, `pt-BR should have "${section}" section`);
        assert.ok(typeof ptBr[section] === "object", `pt-BR.${section} should be an object`);
    }
});

test("Catalog: pt-BR has no empty string values", async () => {
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

test("Catalog: en keys are a subset of pt-BR (no orphan keys)", async () => {
    const ptBr = catalog["pt-BR"];
    const en = catalog.en;

    const missingKeys = checkKeysExist(en, ptBr);
    assert.equal(
        missingKeys.length,
        0,
        `en should only have keys that exist in pt-BR. Orphan keys: ${missingKeys.join(", ")}`
    );
});

test("Catalog: all alert.types keys are consistent", async () => {
    const ptBr = catalog["pt-BR"].alert.types;
    const en = catalog.en.alert.types;

    const enKeys = Object.keys(en).sort();

    // en keys should be a subset of ptBr keys
    for (const key of enKeys) {
        assert.ok(key in ptBr, `Alert type "${key}" exists in en but not in pt-BR`);
    }
});

test("Catalog: no undefined values", async () => {
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

test("Catalog: all values are strings", async () => {
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

test("Catalog (I18N-002): new shell/auth keys resolve to non-empty strings in both locales", async () => {
    // The auth pages + dashboard shell consume exactly these keys (see
    // specs/040-i18n-auth-shell-ptbr/contracts/catalog-keys.md).
    const requiredKeys = [
        "app.title",
        "access.denied_title",
        "access.denied_message",
        "nav.reports",
        "nav.entries",
        "nav.summary",
        "nav.comparison",
        "nav.vendors",
        "nav.documents",
        "nav.units",
        "nav.fines",
        "nav.alerts",
        "nav.runs",
        "auth.sign_in_title",
        "auth.sign_in_description",
        "auth.email_label",
        "auth.password_label",
        "auth.sign_in_email_placeholder",
        "auth.sign_in_button",
        "auth.signing_in",
        "auth.sign_in_error",
        "auth.unexpected_error",
        "auth.no_account_prompt",
        "auth.create_account_link",
        "auth.sign_up_title",
        "auth.sign_up_description",
        "auth.name_label",
        "auth.name_placeholder",
        "auth.confirm_password_label",
        "auth.sign_up_button",
        "auth.signing_up",
        "auth.sign_up_error",
        "auth.email_in_use",
        "auth.invalid_credentials",
        "auth.passwords_no_match",
        "auth.have_account_prompt",
        "auth.sign_in_link",
        "auth.sign_out",
        "auth.signing_out",
        "auth.sign_out_error",
    ];

    for (const locale of ["pt-BR", "en"]) {
        for (const key of requiredKeys) {
            const parts = key.split(".");
            let value = catalog[locale];
            for (const part of parts) {
                assert.ok(
                    value && typeof value === "object" && part in value,
                    `Catalog key "${key}" should exist in locale "${locale}"`
                );
                value = value[part];
            }
            assert.equal(typeof value, "string", `Catalog key "${key}" in "${locale}" should be a string`);
            assert.ok(value.length > 0, `Catalog key "${key}" in "${locale}" should be non-empty`);
        }
    }
});

test("Catalog: pt-BR has complete section structure", async () => {
    const ptBr = catalog["pt-BR"];

    // Expected sections
    const expectedSections = {
        nav: [
            "home",
            "entries",
            "documents",
            "alerts",
            "dashboard",
            "settings",
            "reports",
            "summary",
            "comparison",
            "vendors",
            "units",
            "fines",
            "runs",
        ],
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
            "sign_in_email_placeholder",
            "signing_in",
            "unexpected_error",
            "no_account_prompt",
            "create_account_link",
            "sign_up_title",
            "sign_up_description",
            "name_label",
            "name_placeholder",
            "confirm_password_label",
            "sign_up_button",
            "signing_up",
            "sign_up_error",
            "email_in_use",
            "passwords_no_match",
            "have_account_prompt",
            "sign_in_link",
            "signing_out",
            "sign_out_error",
        ],
        app: ["title"],
        access: ["denied_title", "denied_message"],
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
