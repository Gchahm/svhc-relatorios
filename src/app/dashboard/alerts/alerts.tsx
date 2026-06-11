import { Badge } from "@/components/ui/badge";

/**
 * Entry ids an alert concerns, parsed from its (untyped JSON) metadata. Covers both the
 * per-attachment mismatch alerts (single `entry_id`) and the entry-level alerts that store
 * an `entry_ids` array (duplicate_billing, duplicate_entry, negative_credit,
 * large_expense_no_attachment). Period/category-level alerts have neither → no links.
 * Parses defensively: any malformed/absent metadata yields no links rather than throwing.
 */
export function affectedEntryIds(metadata: string | null): string[] {
    if (!metadata) return [];
    try {
        const meta = JSON.parse(metadata) as { entry_ids?: unknown; entry_id?: unknown };
        if (Array.isArray(meta.entry_ids)) {
            return meta.entry_ids.filter((v): v is string => typeof v === "string");
        }
        if (typeof meta.entry_id === "string") return [meta.entry_id];
        return [];
    } catch {
        return [];
    }
}

/** Deep link to the entries page focused on one entry, with the detail dialog auto-opened. */
export function entryHref(period: string, entryId: string): string {
    return `/dashboard/entries?period=${encodeURIComponent(period)}&entry=${encodeURIComponent(entryId)}`;
}

/** The document an alert references (document_overpayment), for a cross-link to its detail page. */
export function referencedDocumentId(metadata: string | null): string | null {
    if (!metadata) return null;
    try {
        const meta = JSON.parse(metadata) as { document_id?: unknown };
        return typeof meta.document_id === "string" ? meta.document_id : null;
    } catch {
        return null;
    }
}

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
const KEY_LABELS: Record<string, string> = {
    total_value: "Document total",
    sum_entries: "Sum of entries",
    over_amount: "Over amount",
    total: "Total",
    vendor_total: "Vendor total",
    total_expenses: "Total expenses",
    ledger_value: "Ledger value",
    extracted_value: "Extracted value",
    pct: "Share",
    rate_pct: "Rate",
    count: "Count",
    paying: "Paying",
    delinquent: "Delinquent",
    kind: "Kind",
    vendor_name: "Vendor",
    vendor_id: "Vendor id",
    document_number: "Document №",
    issuer_cnpj: "Issuer CNPJ",
    date: "Date",
    description: "Description",
    movement_type: "Movement",
};

function formatCurrency(value: number): string {
    return value.toLocaleString("pt-BR", { style: "currency", currency: "BRL" });
}

function labelFor(key: string): string {
    return KEY_LABELS[key] ?? key.replace(/_/g, " ");
}

function formatValue(key: string, value: unknown): string {
    if (value === null || value === undefined) return "—";
    if (typeof value === "number") {
        if (CURRENCY_KEYS.has(key)) return formatCurrency(value);
        if (PERCENT_KEYS.has(key)) return `${value}%`;
        return String(value);
    }
    if (typeof value === "string" && CURRENCY_KEYS.has(key)) {
        const n = Number(value);
        return Number.isFinite(n) ? formatCurrency(n) : value;
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
export function evidenceFields(metadata: string | null): EvidenceField[] {
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
        .map(k => ({ key: k, label: labelFor(k), value: formatValue(k, meta[k]) }));
}

export function SeverityBadge({ severity }: { severity: string }) {
    if (severity === "critical") {
        return <Badge variant="destructive">{severity}</Badge>;
    }
    if (severity === "warning") {
        return (
            <Badge variant="outline" className="border-yellow-400 text-yellow-700">
                {severity}
            </Badge>
        );
    }
    return <Badge variant="secondary">{severity}</Badge>;
}

export function StatusBadge({ resolved }: { resolved: boolean }) {
    if (resolved) {
        return (
            <Badge variant="outline" className="border-green-400 text-green-700">
                resolved
            </Badge>
        );
    }
    return <Badge variant="destructive">active</Badge>;
}
