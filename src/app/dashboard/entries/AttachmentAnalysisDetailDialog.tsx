"use client";

import { useEffect, useState } from "react";
import { Badge } from "@/components/ui/badge";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import PageImageViewer from "./PageImageViewer";
import type { AttachmentAnalysisRow } from "./types";
import { useTranslation, useLocale } from "@/lib/i18n/client";
import { formatCurrency } from "@/lib/i18n/formatters.client";
import type { SupportedLocale, DeepCatalogKey } from "@/lib/i18n/catalog";

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

// Well-known keys emitted by the VLM prompt, in display order, with friendly label keys.
// The label is a catalog key (chrome, translated); the extraction `key` itself stays verbatim.
const KNOWN_FIELDS: { key: string; labelKey: DeepCatalogKey; currency?: boolean }[] = [
    { key: "valor_total", labelKey: "analysis.field_gross", currency: true },
    { key: "valor_liquido", labelKey: "analysis.field_net", currency: true },
    { key: "valor_pago", labelKey: "analysis.field_paid", currency: true },
    { key: "cnpj_emitente", labelKey: "analysis.field_cnpj" },
    { key: "nome_emitente", labelKey: "analysis.field_issuer" },
    { key: "data_emissao", labelKey: "analysis.field_issue_date" },
    { key: "numero_documento", labelKey: "analysis.field_document_number" },
    { key: "descricao_servico", labelKey: "analysis.field_service" },
    { key: "tipo_documento", labelKey: "analysis.field_doc_type" },
    { key: "papel_artefato", labelKey: "analysis.field_artifact_role" },
];

const KNOWN_KEYS = new Set(KNOWN_FIELDS.map(f => f.key));

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
                        <p className="text-xs text-red-600">
                            {t("analysis.parse_error_prefix")} {record.parseError}
                        </p>
                    )}
                </div>
            );
        }
        return <p className="text-xs italic text-muted-foreground">{t("analysis.no_parsed_values")}</p>;
    }

    const known = KNOWN_FIELDS.map(f => ({ ...f, display: formatValue(values[f.key], locale, f.currency) })).filter(
        f => f.display !== null
    );
    const extraKeys = Object.keys(values).filter(k => !KNOWN_KEYS.has(k) && formatValue(values[k], locale) !== null);

    if (known.length === 0 && extraKeys.length === 0) {
        return <p className="text-xs italic text-muted-foreground">{t("analysis.no_parsed_values")}</p>;
    }

    return (
        <div className="grid grid-cols-2 gap-x-4 gap-y-2 sm:grid-cols-3">
            {known.map(f => (
                <Field key={f.key} label={t(f.labelKey)} value={f.display} t={t} />
            ))}
            {extraKeys.map(k => (
                <Field key={k} label={k} value={formatValue(values[k], locale)} t={t} />
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
                            <div className="rounded-md border border-red-300 bg-red-50 p-3 text-sm text-red-700">
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
                                    <Badge variant="outline" className="border-blue-400 text-blue-700 text-[10px]">
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
                                <p className="text-sm text-red-600">
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
            <Badge variant="outline" className="border-green-400 text-green-700 text-[10px]">
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
