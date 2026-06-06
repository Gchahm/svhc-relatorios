"use client";

import { useEffect, useState } from "react";
import { Badge } from "@/components/ui/badge";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import type { DocAnalysisRow } from "./DocumentAnalysesClient";

interface DocAnalysisRecord {
    id: string;
    analysisType: string;
    pageIndex: number | null;
    pageLabel: string | null;
    artifactRole: string | null;
    response: string | null;
    rawText: string | null;
    parseError: string | null;
}

// Roles whose presence means the roll-up amount was reconciled against a payment artifact,
// per the pipeline's amount precedence (payment_proof paid -> boleto -> invoice net -> gross).
const PAYMENT_ARTIFACT_ROLES = new Set(["payment_proof", "boleto"]);

// Well-known keys emitted by the VLM prompt, in display order, with friendly labels.
const KNOWN_FIELDS: { key: string; label: string; currency?: boolean }[] = [
    { key: "valor_total", label: "Gross", currency: true },
    { key: "valor_liquido", label: "Net", currency: true },
    { key: "valor_pago", label: "Paid", currency: true },
    { key: "cnpj_emitente", label: "CNPJ" },
    { key: "nome_emitente", label: "Issuer" },
    { key: "data_emissao", label: "Issue date" },
    { key: "numero_documento", label: "Document №" },
    { key: "descricao_servico", label: "Service" },
    { key: "tipo_documento", label: "Doc type" },
    { key: "papel_artefato", label: "Artifact role" },
];

const KNOWN_KEYS = new Set(KNOWN_FIELDS.map(f => f.key));

function formatCurrency(value: number) {
    return value.toLocaleString("pt-BR", { style: "currency", currency: "BRL" });
}

function formatValue(value: unknown, currency?: boolean) {
    if (value === null || value === undefined || value === "") return null;
    if (currency && typeof value === "number") return formatCurrency(value);
    if (typeof value === "object") return JSON.stringify(value);
    return String(value);
}

/** Parse a record's stored `response` JSON, falling back to raw text / parse error. */
function parseResponse(record: DocAnalysisRecord): {
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
            // fall through to raw text / parse error
        }
    }
    return { values: null, fallback: record.parseError || record.rawText || null };
}

function pageLabelDisplay(record: DocAnalysisRecord) {
    if (record.pageLabel) return record.pageLabel;
    if (record.pageIndex !== null) return `page ${record.pageIndex + 1}`;
    return "?";
}

function Field({ label, value }: { label: string; value: string | null | undefined }) {
    return (
        <div className="flex flex-col gap-0.5">
            <span className="text-[10px] uppercase tracking-wide text-muted-foreground">{label}</span>
            {value ? (
                <span className="text-sm">{value}</span>
            ) : (
                <span className="text-sm italic text-muted-foreground">not extracted</span>
            )}
        </div>
    );
}

function RecordValues({ record }: { record: DocAnalysisRecord }) {
    const { values, fallback } = parseResponse(record);

    if (!values) {
        if (fallback) {
            return (
                <div className="space-y-1">
                    {record.parseError && <p className="text-xs text-red-600">Parse error: {record.parseError}</p>}
                    {record.rawText && (
                        <pre className="whitespace-pre-wrap break-words rounded bg-muted/50 p-2 text-xs text-muted-foreground">
                            {record.rawText}
                        </pre>
                    )}
                </div>
            );
        }
        return <p className="text-xs italic text-muted-foreground">No parsed values.</p>;
    }

    const known = KNOWN_FIELDS.map(f => ({ ...f, display: formatValue(values[f.key], f.currency) })).filter(
        f => f.display !== null
    );
    const extraKeys = Object.keys(values).filter(k => !KNOWN_KEYS.has(k) && formatValue(values[k]) !== null);

    if (known.length === 0 && extraKeys.length === 0) {
        return <p className="text-xs italic text-muted-foreground">No parsed values.</p>;
    }

    return (
        <div className="grid grid-cols-2 gap-x-4 gap-y-2 sm:grid-cols-3">
            {known.map(f => (
                <Field key={f.key} label={f.label} value={f.display} />
            ))}
            {extraKeys.map(k => (
                <Field key={k} label={k} value={formatValue(values[k])} />
            ))}
        </div>
    );
}

export default function DocumentAnalysisDetailDialog({
    analysis,
    onOpenChange,
}: {
    analysis: DocAnalysisRow | null;
    onOpenChange: (open: boolean) => void;
}) {
    const [records, setRecords] = useState<DocAnalysisRecord[]>([]);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);

    const analysisId = analysis?.id ?? null;

    useEffect(() => {
        if (!analysisId) return;
        let cancelled = false;
        setLoading(true);
        setError(null);
        setRecords([]);
        fetch(`/api/document-analyses/${analysisId}`)
            .then(res => {
                if (!res.ok) throw new Error("Failed to load records");
                return res.json();
            })
            .then((data: DocAnalysisRecord[]) => {
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

    const reconciledAgainstPayment = records.some(r => r.artifactRole && PAYMENT_ARTIFACT_ROLES.has(r.artifactRole));

    return (
        <Dialog open={analysis !== null} onOpenChange={onOpenChange}>
            <DialogContent className="max-h-[85vh] max-w-3xl overflow-y-auto">
                <DialogHeader>
                    <DialogTitle className="flex items-center gap-2">
                        Document Analysis
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
                                <span className="font-medium">Processing error:</span> {analysis.error}
                            </div>
                        )}

                        {/* Roll-up */}
                        <section className="space-y-3">
                            <h3 className="text-sm font-semibold">Roll-up</h3>
                            <div className="grid grid-cols-2 gap-x-4 gap-y-2 sm:grid-cols-3">
                                <Field label="Issuer" value={analysis.issuerName} />
                                <Field label="CNPJ" value={analysis.extractedCnpj} />
                                <Field label="Document №" value={analysis.documentNumber} />
                                <Field label="Service" value={analysis.serviceDescription} />
                                <Field label="Entry amount" value={formatCurrency(analysis.entryAmount)} />
                                <Field
                                    label="Document amount"
                                    value={
                                        analysis.extractedAmount != null
                                            ? formatCurrency(analysis.extractedAmount)
                                            : null
                                    }
                                />
                            </div>
                            <div className="flex flex-wrap items-center gap-2">
                                <MatchPill label="Amount" match={analysis.amountMatch} />
                                <MatchPill label="Vendor" match={analysis.vendorMatch} />
                                <MatchPill label="Date" match={analysis.dateMatch} />
                                {reconciledAgainstPayment && (
                                    <Badge variant="outline" className="border-blue-400 text-blue-700 text-[10px]">
                                        amount reconciled vs payment artifact
                                    </Badge>
                                )}
                            </div>
                        </section>

                        {/* Per-page records */}
                        <section className="space-y-3">
                            <h3 className="text-sm font-semibold">Per-page records</h3>
                            {loading && <p className="text-sm text-muted-foreground">Loading…</p>}
                            {error && <p className="text-sm text-red-600">Error: {error}</p>}
                            {!loading && !error && records.length === 0 && (
                                <p className="text-sm italic text-muted-foreground">
                                    No per-page records for this analysis.
                                </p>
                            )}
                            {!loading &&
                                !error &&
                                records.map(record => (
                                    <div key={record.id} className="rounded-md border p-3 space-y-2">
                                        <div className="flex items-center gap-2">
                                            <Badge variant="secondary" className="text-[10px]">
                                                {pageLabelDisplay(record)}
                                            </Badge>
                                            {record.artifactRole && (
                                                <Badge variant="outline" className="text-[10px]">
                                                    {record.artifactRole}
                                                </Badge>
                                            )}
                                            <span className="text-[10px] text-muted-foreground">
                                                {record.analysisType}
                                            </span>
                                        </div>
                                        <RecordValues record={record} />
                                    </div>
                                ))}
                        </section>
                    </div>
                )}
            </DialogContent>
        </Dialog>
    );
}

function MatchPill({ label, match }: { label: string; match: boolean | null }) {
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
                {label}: OK
            </Badge>
        );
    }
    return (
        <Badge variant="destructive" className="text-[10px]">
            {label}: mismatch
        </Badge>
    );
}
