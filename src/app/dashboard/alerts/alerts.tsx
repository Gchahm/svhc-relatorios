"use client";

import { Badge } from "@/components/ui/badge";
import { useTranslation } from "@/lib/i18n/client";
import { formatCurrency } from "@/lib/i18n/formatters.client";
import type { SupportedLocale, DeepCatalogKey } from "@/lib/i18n/catalog";

// Pure metadata helpers live in a sibling `.ts` so they're unit-testable (feature 045 / TEST-003).
// Re-exported here to keep this module's public surface unchanged.
export { affectedEntryIds, entryHref, referencedDocumentId } from "./alerts-helpers";

// Metadata keys rendered elsewhere (entry links / document link), excluded from the generic grid.
const HANDLED_KEYS = new Set(["entry_ids", "entry_id", "document_id"]);
const CURRENCY_KEYS = new Set([
    "total_value",
    "sum_entries",
    "over_amount",
    "total",
    "vendor_total",
    "total_expenses",
    "ledger_value",
    "extracted_value",
]);
const PERCENT_KEYS = new Set(["pct", "rate_pct"]);
// Metadata keys with a friendly catalog label (`meta.*`). Keys absent here fall back to a
// readable humanized form (underscores → spaces), never raw snake_case.
const META_LABEL_KEYS = new Set([
    "total_value",
    "sum_entries",
    "over_amount",
    "total",
    "vendor_total",
    "total_expenses",
    "ledger_value",
    "extracted_value",
    "pct",
    "rate_pct",
    "count",
    "paying",
    "delinquent",
    "kind",
    "vendor_name",
    "vendor_id",
    "document_number",
    "issuer_cnpj",
    "date",
    "description",
    "movement_type",
]);

/** A translation function (from `useTranslation()` or the server `t`). */
type Translate = (key: DeepCatalogKey) => string;

function labelFor(key: string, t: Translate): string {
    return META_LABEL_KEYS.has(key) ? t(`meta.${key}` as DeepCatalogKey) : key.replace(/_/g, " ");
}

function formatValue(key: string, value: unknown, locale: SupportedLocale): string {
    if (value === null || value === undefined) return "—";
    if (typeof value === "number") {
        if (CURRENCY_KEYS.has(key)) return formatCurrency(value, locale);
        if (PERCENT_KEYS.has(key)) return `${value}%`;
        return String(value);
    }
    if (typeof value === "string" && CURRENCY_KEYS.has(key)) {
        const n = Number(value);
        return Number.isFinite(n) ? formatCurrency(n, locale) : value;
    }
    if (typeof value === "object") return JSON.stringify(value);
    return String(value);
}

export interface EvidenceField {
    key: string;
    label: string;
    value: string;
}

/**
 * Labeled key/value evidence parsed from an alert's metadata — every key except the ones rendered as
 * entry links / a document link. Known keys get friendly labels and currency/percent formatting;
 * unknown keys fall back to a readable string. Malformed metadata → no fields (never throws).
 */
export function evidenceFields(metadata: string | null, t: Translate, locale: SupportedLocale): EvidenceField[] {
    if (!metadata) return [];
    let meta: Record<string, unknown>;
    try {
        const parsed = JSON.parse(metadata);
        if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) return [];
        meta = parsed as Record<string, unknown>;
    } catch {
        return [];
    }
    return Object.keys(meta)
        .filter(k => !HANDLED_KEYS.has(k))
        .map(k => ({ key: k, label: labelFor(k, t), value: formatValue(k, meta[k], locale) }));
}

export function SeverityBadge({ severity }: { severity: string }) {
    const t = useTranslation();
    const label =
        severity === "critical" || severity === "warning" || severity === "info" ? t(`severity.${severity}`) : severity;
    if (severity === "critical") {
        return <Badge variant="destructive">{label}</Badge>;
    }
    if (severity === "warning") {
        return (
            <Badge
                variant="outline"
                className="border-yellow-400 dark:border-yellow-700 text-yellow-700 dark:text-yellow-300"
            >
                {label}
            </Badge>
        );
    }
    return <Badge variant="secondary">{label}</Badge>;
}

export function StatusBadge({ resolved }: { resolved: boolean }) {
    const t = useTranslation();
    if (resolved) {
        return (
            <Badge
                variant="outline"
                className="border-green-400 dark:border-green-700 text-green-700 dark:text-green-400"
            >
                {t("alert_status.resolved")}
            </Badge>
        );
    }
    return <Badge variant="destructive">{t("alert_status.active")}</Badge>;
}
