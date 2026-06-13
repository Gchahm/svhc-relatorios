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
        "detail",
        "analysis",
        "viewer",
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

test("Catalog (I18N-003): dashboard list-page keys resolve to non-empty strings in both locales", async () => {
    // The dashboard list pages + shared filter components consume exactly these keys
    // (see specs/041-i18n-dashboard-lists/contracts/catalog-keys.md).
    const requiredKeys = [
        // page titles/descriptions
        "page.reports_title",
        "page.reports_description",
        "page.fines_title",
        "page.fines_description",
        "page.comparison_title",
        "page.comparison_description",
        "page.summary_title",
        "page.summary_description",
        "page.runs_title",
        "page.runs_description",
        "page.units_title",
        "page.units_description",
        "page.vendors_title",
        "page.vendors_description",
        "page.document_analyses_title",
        "page.document_analyses_description",
        // table headers
        "table.category",
        "table.subcategory",
        "table.unit",
        "table.doc",
        "table.amt",
        "table.vnd",
        "table.dt",
        "table.title",
        "table.severity",
        "table.entries",
        "table.number",
        "table.issuer",
        "table.total",
        "table.sum_entries",
        "table.links",
        "table.revenue",
        "table.expenses",
        "table.month_balance",
        "table.accumulated_balance",
        "table.reason",
        "table.block",
        "table.share",
        "table.run",
        "table.executed_at",
        "table.periods_scraped",
        "table.attachments",
        "table.errors",
        "table.name",
        "table.count",
        "table.difference",
        "table.pct_change",
        "table.subcategories",
        "table.period_base",
        "table.period_compare",
        "table.movement",
        "table.duration_s",
        "table.code",
        "table.total_paid",
        "table.vendor_name",
        "table.pct_of_total",
        "runs.status_success",
        "runs.status_error",
        "runs.status_running",
        "runs.missing_title",
        "runs.missing_message",
        // form
        "form.all",
        "form.all_types",
        "form.search_doc_placeholder",
        "form.search_number_issuer",
        "form.no_alerts",
        "form.no_documents",
        "form.no_entries",
        "form.no_fines",
        "form.no_vendors",
        "form.no_units",
        "form.no_runs",
        "form.all_periods",
        // filter labels
        "filter.period",
        "filter.search",
        "filter.document_type",
        "filter.attachment_status",
        "filter.severity",
        "filter.type",
        "filter.status",
        "filter.block",
        "filter.reason",
        "filter.category",
        "filter.subcategory",
        "filter.categories_subcategories",
        "filter.periods",
        // document reconciliation status
        "status.over",
        "status.within",
        "status.under",
        "status.unknown",
        // alert severity
        "severity.critical",
        "severity.warning",
        "severity.info",
        // alert resolved state
        "alert_status.active",
        "alert_status.resolved",
        // attachment match status
        "match.all_match",
        "match.has_mismatch",
        "match.has_error",
        "match.amount",
        "match.vendor",
        "match.date",
        "match.errors",
        "match.docs",
        // pluralized counts (one/other)
        "count.entries_one",
        "count.entries_other",
        "count.alerts_one",
        "count.alerts_other",
        "count.documents_one",
        "count.documents_other",
        "count.fines_one",
        "count.fines_other",
        "count.periods_one",
        "count.periods_other",
        "count.units_one",
        "count.units_other",
        "count.vendors_one",
        "count.vendors_other",
        "count.runs_one",
        "count.runs_other",
        "count.subcategories_one",
        "count.subcategories_other",
        "count.rows_one",
        "count.rows_other",
        // summary prefixes
        "summary.revenue",
        "summary.expenses",
        "summary.net",
        "summary.total",
        // actions / notices
        "action.open",
        "action.dismiss",
        "notice.deeplink_invalid",
        "notice.deeplink_not_found_prefix",
        "notice.deeplink_not_found_suffix",
        // alert metadata evidence labels
        "meta.total_value",
        "meta.sum_entries",
        "meta.over_amount",
        "meta.total",
        "meta.vendor_total",
        "meta.total_expenses",
        "meta.ledger_value",
        "meta.extracted_value",
        "meta.pct",
        "meta.rate_pct",
        "meta.count",
        "meta.paying",
        "meta.delinquent",
        "meta.kind",
        "meta.vendor_name",
        "meta.vendor_id",
        "meta.document_number",
        "meta.issuer_cnpj",
        "meta.date",
        "meta.description",
        "meta.movement_type",
        // error prefix + list row chrome
        "error.generic_prefix",
        "list.open_attachment_detail",
        "list.open_alert_detail",
        "list.open_document_detail",
        "list.entry_n",
        "list.documents_subtitle",
        "list.doc_fallback",
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

test("Catalog (I18N-004): detail-surface keys resolve to non-empty strings in both locales", async () => {
    // The detail pages, the attachment-analysis dialog, and the page-image viewer consume exactly
    // these keys (see specs/042-i18n-detail-surfaces/data-model.md).
    const requiredKeys = [
        // shared detail-page chrome
        "detail.loading",
        "detail.back_to_alerts",
        "detail.back_to_documents",
        "detail.alert_not_found",
        "detail.document_not_found",
        "detail.error_prefix",
        "detail.unknown_error",
        "detail.field_type",
        "detail.field_period",
        "detail.field_created",
        "detail.field_resolved_at",
        "detail.field_description",
        "detail.field_notes",
        "detail.section_resolution",
        "detail.resolved_message",
        "detail.reopen_alert",
        "detail.reopening",
        "detail.notes_optional_label",
        "detail.notes_placeholder",
        "detail.resolve_alert",
        "detail.resolving",
        "detail.section_evidence",
        "detail.view_referenced_document",
        "detail.section_affected_entries",
        "detail.no_entries_linked",
        "detail.field_category",
        "detail.field_subcategory",
        "detail.field_vendor",
        "detail.field_unit",
        "detail.field_amount",
        "detail.view_attachment",
        "detail.view_attachment_title",
        "detail.no_attachment_analysis",
        "detail.documents_button",
        "detail.attached_documents",
        "detail.no_documents_linked_entry",
        "detail.field_issuer",
        "detail.field_cnpj",
        "detail.field_total",
        "detail.field_sum_entries",
        "detail.field_linked_entries",
        "detail.section_document_image",
        "detail.no_image_available",
        "detail.document_fallback",
        "detail.section_source_attachments",
        "detail.from_entry",
        "detail.no_image_for_source",
        "detail.this_document",
        "detail.unlabeled",
        "detail.section_linked_entries",
        "detail.no_entries_linked_plain",
        "detail.col_period",
        "detail.col_date",
        "detail.col_description",
        "detail.col_category",
        "detail.col_vendor",
        "detail.col_unit",
        "detail.col_amount",
        "detail.col_open",
        "detail.open",
        "detail.section_related_documents",
        "detail.no_related_documents",
        "detail.col_number",
        "detail.col_issuer",
        "detail.col_type",
        "detail.col_total",
        "detail.col_status",
        // attachment-analysis dialog
        "analysis.dialog_title",
        "analysis.processing_error",
        "analysis.section_entry_source",
        "analysis.section_rollup",
        "analysis.section_pages",
        "analysis.field_category",
        "analysis.field_subcategory",
        "analysis.field_vendor",
        "analysis.field_date",
        "analysis.field_description",
        "analysis.field_issuer",
        "analysis.field_cnpj",
        "analysis.field_document_number",
        "analysis.field_service",
        "analysis.field_entry_amount",
        "analysis.field_document_amount",
        "analysis.field_gross",
        "analysis.field_net",
        "analysis.field_paid",
        "analysis.field_issue_date",
        "analysis.field_doc_type",
        "analysis.field_artifact_role",
        "analysis.match_amount",
        "analysis.match_vendor",
        "analysis.match_date",
        "analysis.match_ok",
        "analysis.match_mismatch",
        "analysis.reconciled_vs_payment",
        "analysis.not_extracted",
        "analysis.no_parsed_values",
        "analysis.parse_error_prefix",
        "analysis.no_pages_or_records",
        "analysis.page_n",
        // page-image viewer
        "viewer.image_unavailable",
        "viewer.enlarge",
        "viewer.page_alt",
        "viewer.page_alt_role",
        "viewer.document_image_alt",
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

    // Interpolation templates must keep their placeholder tokens.
    assert.ok(catalog["pt-BR"].analysis.page_n.includes("{n}"), "analysis.page_n must keep {n}");
    assert.ok(catalog["pt-BR"].viewer.enlarge.includes("{alt}"), "viewer.enlarge must keep {alt}");
    assert.ok(catalog["pt-BR"].viewer.page_alt.includes("{label}"), "viewer.page_alt must keep {label}");
    assert.ok(
        catalog["pt-BR"].viewer.page_alt_role.includes("{label}") &&
            catalog["pt-BR"].viewer.page_alt_role.includes("{role}"),
        "viewer.page_alt_role must keep {label} and {role}"
    );
    assert.ok(
        catalog["pt-BR"].viewer.document_image_alt.includes("{type}"),
        "viewer.document_image_alt must keep {type}"
    );
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
