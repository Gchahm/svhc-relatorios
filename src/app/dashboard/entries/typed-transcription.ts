/**
 * Pure builder for the type-aware extraction view (feature 057 / EXTRACT-006).
 *
 * Turns a stored TYPED transcription (`page_classifications.response` / `attachment_analysis_records.response`
 * carrying a `doc_type` discriminator — feature 055 / EXTRACT-004) into an ordered list of display
 * sections grouped by the document's natural structure, with the deterministic reconciliation
 * mapper's SOURCE fields tagged with the role they feed (provenance).
 *
 * This module is the single TypeScript source of truth for the provenance map. It MIRRORS — it does
 * NOT import — `scripts/analysis/type_mappers.py` (TS cannot import Python; the repo mirrors
 * cross-language invariants the same way the scraper mirrors the analysis reconciliation tolerance).
 * `src/app/dashboard/entries/typed-transcription.test.mjs` pins the map against
 * `specs/057-type-aware-extraction-ui/contracts/provenance.md` so the UI cannot drift from the mapper.
 *
 * No React import beyond types — kept pure so it is unit-testable with `node --test` / `.test.mjs`
 * (mirrors `deeplinkView.ts` / `deeplinkView.test.mjs`).
 */

import { formatCurrencyFor } from "../../../lib/i18n/formatters.core.ts";
import type { SupportedLocale, DeepCatalogKey } from "../../../lib/i18n/catalog.ts";

type Translate = (key: DeepCatalogKey) => string;

// The six canonical corpus document types (mirrors tools/doc_transcribe registry DOC_TYPES).
export type DocType = "danfe" | "nfse" | "boleto" | "recibo" | "comprovante_pagamento" | "outro";

// Reconciliation roles a transcribed field can feed (mirrors type_mappers.py outputs).
export type ReconRole = "total" | "issuer_name" | "issuer_cnpj" | "number" | "date" | "service";

export interface TypedRow {
    /** Dotted source path, stable key (e.g. `valores.valor_liquido`, `itens.0.descricao`). */
    path: string;
    /** Localized label when the leaf key is known; else the verbatim path/segment. */
    label: string;
    /** Display string (currency-formatted for known amount leaves). */
    value: string;
    /** Set iff this path is the reconciliation mapper's source for that role. */
    provenanceRole?: ReconRole;
    /** True for full-width long-text rows (e.g. raw_text, discriminacao_servico). */
    wide?: boolean;
}

export interface TypedSection {
    /** Section identity (top-level object key, or "general" for top-level scalars). */
    key: string;
    /** Localized section title when known; else the verbatim key. */
    title: string;
    rows: TypedRow[];
}

// ─── Canonical type resolution (mirrors type_mappers._canonical_doc_type) ───────────────────────

const DOC_TYPES: ReadonlySet<string> = new Set(["danfe", "nfse", "boleto", "recibo", "comprovante_pagamento", "outro"]);

const ALIASES: Record<string, DocType> = {
    danfe: "danfe",
    "nf e": "danfe",
    nfe: "danfe",
    "nota fiscal": "danfe",
    "nota fiscal eletronica": "danfe",
    invoice: "danfe",
    nfse: "nfse",
    "nfs e": "nfse",
    danfse: "nfse",
    "nota fiscal de servico": "nfse",
    boleto: "boleto",
    "boleto bancario": "boleto",
    recibo: "recibo",
    "comprovante pagamento": "comprovante_pagamento",
    comprovante: "comprovante_pagamento",
    "comprovante de pagamento": "comprovante_pagamento",
    "payment proof": "comprovante_pagamento",
    pix: "comprovante_pagamento",
    ted: "comprovante_pagamento",
    outro: "outro",
    other: "outro",
};

function normalize(raw: string): string {
    return raw.trim().toLowerCase().replace(/[_-]/g, " ").replace(/\s+/g, " ");
}

/** Resolve a `doc_type` / alias to a canonical key; unknown/empty → "outro". Never throws. */
export function canonicalDocType(value: unknown): DocType {
    if (typeof value !== "string" || !value) return "outro";
    if (DOC_TYPES.has(value)) return value as DocType;
    return ALIASES[normalize(value)] ?? "outro";
}

// ─── Reconciliation provenance (mirrors type_mappers.py — see contracts/provenance.md) ──────────
// Per-type map: reconciliation role → dotted SOURCE path in the typed transcription. A `—` in the
// contract table is simply an absent key here. Array-first-element targets use the `.0.` segment.

export const RECONCILIATION_PROVENANCE: Record<DocType, Partial<Record<ReconRole, string>>> = {
    danfe: {
        total: "totais.valor_total_nota",
        issuer_name: "emitente.nome",
        issuer_cnpj: "emitente.cnpj",
        number: "numero",
        date: "data_emissao",
        service: "itens.0.descricao",
    },
    nfse: {
        total: "valores.valor_liquido",
        issuer_name: "prestador.nome",
        issuer_cnpj: "prestador.cnpj",
        number: "numero",
        date: "data_emissao",
        service: "discriminacao_servico",
    },
    boleto: {
        total: "valor_documento",
        issuer_name: "beneficiario.nome",
        issuer_cnpj: "beneficiario.cnpj_cpf",
        number: "numero_documento",
        date: "data_documento",
    },
    recibo: {
        total: "valor",
        issuer_name: "recebedor.nome",
        issuer_cnpj: "recebedor.cnpj_cpf",
        number: "numero",
        date: "data",
        service: "referente_a",
    },
    comprovante_pagamento: {
        total: "valor",
        issuer_name: "recebedor.nome",
        issuer_cnpj: "recebedor.cnpj_cpf",
        number: "identificador",
        date: "data",
    },
    outro: {
        total: "valores_identificados.0.valor",
        service: "descricao",
    },
};

// ─── Display chrome maps ────────────────────────────────────────────────────────────────────────

// Top-level nested-object keys → section title catalog key. Unknown keys keep their verbatim name.
const SECTION_TITLE_KEY: Record<string, DeepCatalogKey> = {
    emitente: "analysis.tsection_issuer",
    prestador: "analysis.tsection_provider",
    beneficiario: "analysis.tsection_issuer",
    recebedor: "analysis.tsection_issuer",
    destinatario: "analysis.tsection_recipient",
    tomador: "analysis.tsection_recipient",
    pagador: "analysis.tsection_payer",
    valores: "analysis.tsection_values",
    totais: "analysis.tsection_totals",
    retencoes: "analysis.tsection_retentions",
    banco: "analysis.tsection_bank",
    itens: "analysis.tsection_items",
    duplicatas: "analysis.tsection_duplicates",
    valores_identificados: "analysis.tsection_identified_values",
};

const ROLE_LABEL_KEY: Record<ReconRole, DeepCatalogKey> = {
    total: "analysis.provenance_total",
    issuer_name: "analysis.provenance_issuer",
    issuer_cnpj: "analysis.provenance_issuer",
    number: "analysis.provenance_number",
    date: "analysis.provenance_date",
    service: "analysis.provenance_service",
};

/** Localized label for a provenance role (used by the component for the badge). */
export function provenanceRoleLabel(role: ReconRole, t: Translate): string {
    return t(ROLE_LABEL_KEY[role]);
}

// Leaf key names that hold a currency amount → format as currency when numeric.
const AMOUNT_LEAF = new Set([
    "valor",
    "valor_documento",
    "valor_total_nota",
    "valor_servico",
    "valor_liquido",
    "valor_iss",
    "base_calculo",
    "deducoes",
    "irrf",
    "inss",
    "csll",
    "pis",
    "cofins",
    "iss",
    "valor_unitario",
    "valor_bruto",
]);

// Long verbatim-text leaves rendered full width.
const WIDE_LEAF = new Set(["raw_text", "discriminacao_servico", "endereco", "linha_digitavel", "codigo_barras"]);

// Discriminator/version chrome — not document content, never displayed.
const HIDDEN_TOP_KEYS = new Set(["doc_type", "schema_version"]);

// ─── Builder ──────────────────────────────────────────────────────────────────────────────────

function formatLeaf(key: string, raw: unknown, locale: SupportedLocale): string | null {
    if (raw === null || raw === undefined || raw === "") return null;
    if (typeof raw === "number" && AMOUNT_LEAF.has(key)) return formatCurrencyFor(raw, locale);
    if (typeof raw === "boolean") return raw ? "true" : "false";
    if (typeof raw === "object") return JSON.stringify(raw);
    return String(raw);
}

/** Reverse lookup: which role (if any) does `path` feed for this type? */
function roleForPath(provenance: Partial<Record<ReconRole, string>>, path: string): ReconRole | undefined {
    for (const [role, src] of Object.entries(provenance) as [ReconRole, string][]) {
        if (src === path) return role;
    }
    return undefined;
}

/**
 * Recursively flatten a value into rows under `parentPath`, tagging provenance by exact path.
 * Nested objects/arrays recurse with a dotted path; scalars become a single row.
 */
function flattenValue(
    value: unknown,
    parentPath: string,
    leafKey: string,
    provenance: Partial<Record<ReconRole, string>>,
    locale: SupportedLocale
): TypedRow[] {
    if (Array.isArray(value)) {
        const rows: TypedRow[] = [];
        value.forEach((item, i) => {
            rows.push(...flattenValue(item, `${parentPath}.${i}`, leafKey, provenance, locale));
        });
        return rows;
    }
    if (value && typeof value === "object") {
        const rows: TypedRow[] = [];
        for (const [k, v] of Object.entries(value as Record<string, unknown>)) {
            rows.push(...flattenValue(v, parentPath ? `${parentPath}.${k}` : k, k, provenance, locale));
        }
        return rows;
    }
    const display = formatLeaf(leafKey, value, locale);
    if (display === null) return [];
    return [
        {
            path: parentPath,
            // Label is the verbatim leaf path segment(s); the path itself is the most honest label
            // for arbitrary nested keys (the section title carries the human grouping).
            label: parentPath,
            value: display,
            provenanceRole: roleForPath(provenance, parentPath),
            wide: WIDE_LEAF.has(leafKey),
        },
    ];
}

function sectionTitle(key: string, t: Translate): string {
    const labelKey = SECTION_TITLE_KEY[key];
    return labelKey ? t(labelKey) : key;
}

/**
 * Build the ordered display sections for a typed transcription. Never throws on a partial/odd shape:
 * a null/non-object section is skipped, a section with no non-empty rows is omitted, unknown keys
 * keep verbatim labels (nothing dropped). `doc_type`/`schema_version` are hidden; `raw_text` is a
 * leading full-width row.
 */
export function buildTypedSections(
    values: Record<string, unknown>,
    t: Translate,
    locale: SupportedLocale
): TypedSection[] {
    const docType = canonicalDocType(values["doc_type"]);
    const provenance = RECONCILIATION_PROVENANCE[docType] ?? {};

    const sections: TypedSection[] = [];
    const generalRows: TypedRow[] = [];

    for (const [key, value] of Object.entries(values)) {
        if (HIDDEN_TOP_KEYS.has(key)) continue;

        if (value && typeof value === "object") {
            // Nested object or array → its own section.
            const rows = flattenValue(value, key, key, provenance, locale);
            if (rows.length > 0) {
                sections.push({ key, title: sectionTitle(key, t), rows });
            }
            continue;
        }

        // Top-level scalar → general section.
        const display = formatLeaf(key, value, locale);
        if (display !== null) {
            generalRows.push({
                path: key,
                label: key,
                value: display,
                provenanceRole: roleForPath(provenance, key),
                wide: WIDE_LEAF.has(key),
            });
        }
    }

    // The general (top-level-scalar) section leads, if it has any rows.
    if (generalRows.length > 0) {
        sections.unshift({ key: "general", title: t("analysis.tsection_general"), rows: generalRows });
    }

    return sections;
}
