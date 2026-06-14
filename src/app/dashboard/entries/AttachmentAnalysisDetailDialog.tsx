"use client";

import { useEffect, useState } from "react";
import { Badge } from "@/components/ui/badge";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import PageImageViewer from "./PageImageViewer";
import type { AttachmentAnalysisRow } from "./types";
import { useTranslation, useLocale } from "@/lib/i18n/client";
import { formatCurrency } from "@/lib/i18n/formatters.client";
import type { SupportedLocale, DeepCatalogKey } from "@/lib/i18n/catalog";
import { buildTypedSections, provenanceRoleLabel, type TypedRow } from "./typed-transcription";

type Translate = (key: DeepCatalogKey) => string;

interface AttachmentAnalysisRecord {
    id: string;
    analysisType: string;
    pageIndex: number | null;
    pageLabel: string | null;
    artifactRole: string | null;
    response: string | null;
    parseError: string | null;
}

interface PageInfo {
    pageIndex: number;
    pageLabel: string;
    ext: string;
    imageUrl: string;
}

// Roles whose presence means the roll-up amount was reconciled against a payment artifact,
// per the pipeline's amount precedence (payment_proof paid -> boleto -> invoice net -> gross).
const PAYMENT_ARTIFACT_ROLES = new Set(["payment_proof", "boleto"]);

function formatValue(value: unknown, locale: SupportedLocale, currency?: boolean) {
    if (value === null || value === undefined || value === "") return null;
    if (currency && typeof value === "number") return formatCurrency(value, locale);
    if (typeof value === "object") return JSON.stringify(value);
    return String(value);
}

/** Parse a record's stored `response` JSON, falling back to the parse error. */
function parseResponse(record: AttachmentAnalysisRecord): {
    values: Record<string, unknown> | null;
    fallback: string | null;
} {
    if (record.response) {
        try {
            const parsed = JSON.parse(record.response);
            if (parsed && typeof parsed === "object" && !Array.isArray(parsed)) {
                return { values: parsed as Record<string, unknown>, fallback: null };
            }
        } catch {
            // fall through to the parse error
        }
    }
    return { values: null, fallback: record.parseError || null };
}

// Flatten a typed transcription into displayable label/value rows: scalars become `label = value`,
// nested objects expand with a dotted label (`prestador.cnpj`), arrays/objects without scalars fall
// back to a compact JSON string. Defensive: never throws on an odd/partial shape.
function flattenTyped(
    obj: Record<string, unknown>,
    locale: SupportedLocale,
    prefix = ""
): { label: string; value: string }[] {
    const rows: { label: string; value: string }[] = [];
    for (const [key, raw] of Object.entries(obj)) {
        const label = prefix ? `${prefix}.${key}` : key;
        if (raw && typeof raw === "object" && !Array.isArray(raw)) {
            rows.push(...flattenTyped(raw as Record<string, unknown>, locale, label));
            continue;
        }
        const display = formatValue(raw, locale);
        if (display !== null) rows.push({ label, value: display });
    }
    return rows;
}

function pageLabelDisplay(record: AttachmentAnalysisRecord, t: Translate) {
    if (record.pageLabel) return record.pageLabel;
    if (record.pageIndex !== null) return t("analysis.page_n").replace("{n}", String(record.pageIndex + 1));
    return "?";
}

function Field({ label, value, t }: { label: string; value: string | null | undefined; t: Translate }) {
    return (
        <div className="flex flex-col gap-0.5">
            <span className="text-[10px] uppercase tracking-wide text-muted-foreground">{label}</span>
            {value ? (
                <span className="text-sm">{value}</span>
            ) : (
                <span className="text-sm italic text-muted-foreground">{t("analysis.not_extracted")}</span>
            )}
        </div>
    );
}

// A typed-transcription row: the verbatim field plus, when this field is the reconciliation
// mapper's source for a role, a small role badge marking the provenance (feature 057).
function TypedFieldRow({ row, t }: { row: TypedRow; t: Translate }) {
    return (
        <div className={`flex flex-col gap-0.5${row.wide ? " col-span-2 sm:col-span-3" : ""}`}>
            <span className="flex items-center gap-1 text-[10px] uppercase tracking-wide text-muted-foreground">
                {row.label}
                {row.provenanceRole && (
                    <Badge
                        variant="outline"
                        className="border-blue-400 dark:border-blue-700 text-blue-700 dark:text-blue-400 text-[9px] px-1 py-0 font-normal normal-case"
                    >
                        {provenanceRoleLabel(row.provenanceRole, t)}
                    </Badge>
                )}
            </span>
            <span className={`text-sm${row.wide ? " whitespace-pre-wrap break-words" : ""}`}>{row.value}</span>
        </div>
    );
}

function RecordValues({
    record,
    t,
    locale,
}: {
    record: AttachmentAnalysisRecord;
    t: Translate;
    locale: SupportedLocale;
}) {
    const { values, fallback } = parseResponse(record);

    if (!values) {
        if (fallback) {
            return (
                <div className="space-y-1">
                    {record.parseError && (
                        <p className="text-xs text-red-600 dark:text-red-400">
                            {t("analysis.parse_error_prefix")} {record.parseError}
                        </p>
                    )}
                </div>
            );
        }
        return <p className="text-xs italic text-muted-foreground">{t("analysis.no_parsed_values")}</p>;
    }

    // Typed transcription (EXTRACT-006/007 — the only stored shape): render the full transcription
    // grouped by the document's natural structure, with the reconciliation mapper's source fields
    // tagged with the role they feed (provenance). The grouping/provenance live in the pure
    // `buildTypedSections` builder; a defensive try/catch degrades to a flat flatten so an odd shape
    // can never blank the dialog.
    let sections;
    try {
        sections = buildTypedSections(values, t, locale);
    } catch {
        sections = null;
    }
    if (sections === null) {
        const rows = flattenTyped(values, locale);
        if (rows.length === 0) {
            return <p className="text-xs italic text-muted-foreground">{t("analysis.no_parsed_values")}</p>;
        }
        return (
            <div className="space-y-2">
                <span className="text-[10px] font-medium uppercase tracking-wide text-muted-foreground">
                    {t("analysis.full_transcription")}
                </span>
                <div className="grid grid-cols-2 gap-x-4 gap-y-2 sm:grid-cols-3">
                    {rows.map(r => (
                        <Field key={r.label} label={r.label} value={r.value} t={t} />
                    ))}
                </div>
            </div>
        );
    }
    if (sections.length === 0) {
        return <p className="text-xs italic text-muted-foreground">{t("analysis.no_parsed_values")}</p>;
    }
    return (
        <div className="space-y-3">
            <span className="text-[10px] font-medium uppercase tracking-wide text-muted-foreground">
                {t("analysis.full_transcription")}
            </span>
            {sections.map(section => (
                <div key={section.key} className="space-y-1.5">
                    <span className="text-[11px] font-semibold">{section.title}</span>
                    <div className="grid grid-cols-2 gap-x-4 gap-y-2 sm:grid-cols-3">
                        {section.rows.map(row => (
                            <TypedFieldRow key={row.path} row={row} t={t} />
                        ))}
                    </div>
                </div>
            ))}
        </div>
    );
}

export default function AttachmentAnalysisDetailDialog({
    analysis,
    onOpenChange,
}: {
    analysis: AttachmentAnalysisRow | null;
    onOpenChange: (open: boolean) => void;
}) {
    const t = useTranslation();
    const locale = useLocale();
    const [records, setRecords] = useState<AttachmentAnalysisRecord[]>([]);
    const [pages, setPages] = useState<PageInfo[]>([]);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);

    const analysisId = analysis?.id ?? null;

    useEffect(() => {
        if (!analysisId) return;
        let cancelled = false;
        setLoading(true);
        setError(null);
        setRecords([]);
        fetch(`/api/attachment-analyses/${analysisId}`)
            .then(res => {
                if (!res.ok) throw new Error("load-failed");
                return res.json();
            })
            .then((data: AttachmentAnalysisRecord[]) => {
                if (!cancelled) setRecords(data);
            })
            .catch(e => {
                if (!cancelled) setError(e.message);
            })
            .finally(() => {
                if (!cancelled) setLoading(false);
            });
        return () => {
            cancelled = true;
        };
    }, [analysisId]);

    // Page images load independently from the per-page records: a failure here must never block
    // the extracted fields from rendering (FR-007). A missing/failed list simply yields no gallery.
    useEffect(() => {
        if (!analysisId) return;
        let cancelled = false;
        setPages([]);
        fetch(`/api/attachment-analyses/${analysisId}/pages`)
            .then(res => (res.ok ? res.json() : []))
            .then((data: PageInfo[]) => {
                if (!cancelled) setPages(Array.isArray(data) ? data : []);
            })
            .catch(() => {
                if (!cancelled) setPages([]);
            });
        return () => {
            cancelled = true;
        };
    }, [analysisId]);

    const reconciledAgainstPayment = records.some(r => r.artifactRole && PAYMENT_ARTIFACT_ROLES.has(r.artifactRole));

    // Associate each page image with its extracted record (by page index, falling back to label).
    // Pages drive the gallery; records with no matching page still render below (no image).
    const matchedRecordIds = new Set<string>();
    const pageEntries = pages.map(page => {
        const record = records.find(
            r =>
                (r.pageIndex !== null && r.pageIndex === page.pageIndex) ||
                (r.pageLabel !== null && r.pageLabel === page.pageLabel)
        );
        if (record) matchedRecordIds.add(record.id);
        return { page, record };
    });
    const orphanRecords = records.filter(r => !matchedRecordIds.has(r.id));

    return (
        <Dialog open={analysis !== null} onOpenChange={onOpenChange}>
            <DialogContent className="max-h-[85vh] max-w-3xl overflow-y-auto">
                <DialogHeader>
                    <DialogTitle className="flex items-center gap-2">
                        {t("analysis.dialog_title")}
                        {analysis?.documentType && (
                            <Badge variant="outline" className="text-xs font-normal">
                                {analysis.documentType}
                            </Badge>
                        )}
                    </DialogTitle>
                </DialogHeader>

                {analysis && (
                    <div className="space-y-6">
                        {/* Processing error */}
                        {analysis.error && (
                            <div className="rounded-md border border-red-300 dark:border-red-800 bg-red-50 dark:bg-red-950/40 p-3 text-sm text-red-700 dark:text-red-400">
                                <span className="font-medium">{t("analysis.processing_error")}</span> {analysis.error}
                            </div>
                        )}

                        {/* Entry (source) — for cross-checking against the original record */}
                        <section className="space-y-3">
                            <h3 className="text-sm font-semibold">{t("analysis.section_entry_source")}</h3>
                            <div className="grid grid-cols-2 gap-x-4 gap-y-2 sm:grid-cols-3">
                                <Field label={t("analysis.field_category")} value={analysis.categoryName} t={t} />
                                <Field label={t("analysis.field_subcategory")} value={analysis.subcategoryName} t={t} />
                                <Field label={t("analysis.field_vendor")} value={analysis.vendorName} t={t} />
                                <Field label={t("analysis.field_date")} value={analysis.entryDate} t={t} />
                                <Field
                                    label={t("analysis.field_description")}
                                    value={analysis.entryDescription}
                                    t={t}
                                />
                            </div>
                        </section>

                        {/* Roll-up */}
                        <section className="space-y-3">
                            <h3 className="text-sm font-semibold">{t("analysis.section_rollup")}</h3>
                            <div className="grid grid-cols-2 gap-x-4 gap-y-2 sm:grid-cols-3">
                                <Field label={t("analysis.field_issuer")} value={analysis.issuerName} t={t} />
                                <Field label={t("analysis.field_cnpj")} value={analysis.extractedCnpj} t={t} />
                                <Field
                                    label={t("analysis.field_document_number")}
                                    value={analysis.documentNumber}
                                    t={t}
                                />
                                <Field label={t("analysis.field_service")} value={analysis.serviceDescription} t={t} />
                                <Field
                                    label={t("analysis.field_entry_amount")}
                                    value={formatCurrency(analysis.entryAmount, locale)}
                                    t={t}
                                />
                                <Field
                                    label={t("analysis.field_document_amount")}
                                    value={
                                        analysis.extractedAmount != null
                                            ? formatCurrency(analysis.extractedAmount, locale)
                                            : null
                                    }
                                    t={t}
                                />
                            </div>
                            <div className="flex flex-wrap items-center gap-2">
                                <MatchPill label={t("analysis.match_amount")} match={analysis.amountMatch} t={t} />
                                <MatchPill label={t("analysis.match_vendor")} match={analysis.vendorMatch} t={t} />
                                <MatchPill label={t("analysis.match_date")} match={analysis.dateMatch} t={t} />
                                {reconciledAgainstPayment && (
                                    <Badge
                                        variant="outline"
                                        className="border-blue-400 dark:border-blue-700 text-blue-700 dark:text-blue-400 text-[10px]"
                                    >
                                        {t("analysis.reconciled_vs_payment")}
                                    </Badge>
                                )}
                            </div>
                        </section>

                        {/* Pages — page image alongside its extracted record */}
                        <section className="space-y-3">
                            <h3 className="text-sm font-semibold">{t("analysis.section_pages")}</h3>
                            {loading && <p className="text-sm text-muted-foreground">{t("detail.loading")}</p>}
                            {error && (
                                <p className="text-sm text-red-600 dark:text-red-400">
                                    {t("detail.error_prefix")} {t("error.loading_failed")}
                                </p>
                            )}
                            {!loading && !error && pageEntries.length === 0 && orphanRecords.length === 0 && (
                                <p className="text-sm italic text-muted-foreground">
                                    {t("analysis.no_pages_or_records")}
                                </p>
                            )}
                            {pageEntries.map(({ page, record }) => (
                                <div key={page.pageLabel} className="rounded-md border p-3 space-y-2">
                                    <div className="flex items-center gap-2">
                                        <Badge variant="secondary" className="text-[10px]">
                                            {record ? pageLabelDisplay(record, t) : page.pageLabel}
                                        </Badge>
                                        {record?.artifactRole && (
                                            <Badge variant="outline" className="text-[10px]">
                                                {record.artifactRole}
                                            </Badge>
                                        )}
                                        {record && (
                                            <span className="text-[10px] text-muted-foreground">
                                                {record.analysisType}
                                            </span>
                                        )}
                                    </div>
                                    <PageImageViewer
                                        src={page.imageUrl}
                                        alt={t("viewer.page_alt").replace("{label}", page.pageLabel)}
                                    />
                                    {record && <RecordValues record={record} t={t} locale={locale} />}
                                </div>
                            ))}
                            {/* Records with no matching page image (e.g. representative-only extractions) */}
                            {orphanRecords.map(record => (
                                <div key={record.id} className="rounded-md border p-3 space-y-2">
                                    <div className="flex items-center gap-2">
                                        <Badge variant="secondary" className="text-[10px]">
                                            {pageLabelDisplay(record, t)}
                                        </Badge>
                                        {record.artifactRole && (
                                            <Badge variant="outline" className="text-[10px]">
                                                {record.artifactRole}
                                            </Badge>
                                        )}
                                        <span className="text-[10px] text-muted-foreground">{record.analysisType}</span>
                                    </div>
                                    <RecordValues record={record} t={t} locale={locale} />
                                </div>
                            ))}
                        </section>
                    </div>
                )}
            </DialogContent>
        </Dialog>
    );
}

function MatchPill({ label, match, t }: { label: string; match: boolean | null; t: Translate }) {
    if (match === null) {
        return (
            <Badge variant="outline" className="text-[10px] text-muted-foreground">
                {label}: —
            </Badge>
        );
    }
    if (match) {
        return (
            <Badge
                variant="outline"
                className="border-green-400 dark:border-green-700 text-green-700 dark:text-green-400 text-[10px]"
            >
                {label}: {t("analysis.match_ok")}
            </Badge>
        );
    }
    return (
        <Badge variant="destructive" className="text-[10px]">
            {label}: {t("analysis.match_mismatch")}
        </Badge>
    );
}
