"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { ArrowLeft, ExternalLink, FileText, ImageOff } from "lucide-react";
import { StatusBadge } from "../StatusBadge";
import PageImageViewer from "../../entries/PageImageViewer";
import type { DocumentStatus } from "@/lib/documents";

interface LinkedEntry {
    entryId: string;
    period: string;
    date: string;
    description: string;
    amount: number;
    category: string | null;
    subcategory: string | null;
    vendor: string | null;
    unitCode: string | null;
    sourceAttachmentId: string | null;
}

interface SourcePage {
    pageLabel: string;
    pageIndex: number;
    imageUrl: string;
    artifactRole: string | null;
    roleLabel: string | null;
    isDocument: boolean;
}

interface ImageSource {
    attachmentId: string;
    analysisId: string;
    entryId: string;
    period: string;
    documentPageLabel: string | null;
    pages: SourcePage[];
}

interface RelatedDocument {
    id: string;
    documentNumber: string;
    issuerCnpj: string;
    issuerName: string | null;
    documentType: string | null;
    totalValue: number | null;
    sumEntries: number;
    status: DocumentStatus;
}

interface DocumentDetail {
    id: string;
    documentNumber: string;
    issuerCnpj: string;
    issuerName: string | null;
    documentType: string | null;
    totalValue: number | null;
    sumEntries: number;
    status: DocumentStatus;
    entries: LinkedEntry[];
    imageSources: ImageSource[];
    relatedDocuments: RelatedDocument[];
}

function formatCurrency(value: number | null): string {
    if (value === null) return "—";
    return value.toLocaleString("pt-BR", { style: "currency", currency: "BRL" });
}

/** Deep link to the entries page focused on one entry (feature 018). */
function entryHref(period: string, entryId: string): string {
    return `/dashboard/entries?period=${encodeURIComponent(period)}&entry=${encodeURIComponent(entryId)}`;
}

/** The page within each provenance bundle that IS this document (flagged by the API). */
function representativePage(sources: ImageSource[]): SourcePage | null {
    for (const s of sources) {
        const p = s.pages.find(pg => pg.isDocument);
        if (p) return p;
    }
    for (const s of sources) {
        if (s.pages.length > 0) return s.pages[0];
    }
    return null;
}

/** One page thumbnail with its artifact-role label and a marker when it is the document itself. */
function LabeledPage({ page }: { page: SourcePage }) {
    return (
        <div className={`space-y-1 rounded-md border p-2 ${page.isDocument ? "ring-2 ring-blue-400" : ""}`}>
            <div className="flex items-center gap-1.5">
                {page.isDocument && (
                    <Badge variant="outline" className="border-blue-400 text-[10px] text-blue-700">
                        this document
                    </Badge>
                )}
                <Badge variant="secondary" className="text-[10px]">
                    {page.roleLabel ?? "Unlabeled"}
                </Badge>
                <span className="text-[10px] text-muted-foreground">{page.pageLabel}</span>
            </div>
            <PageImageViewer src={page.imageUrl} alt={`Page ${page.pageLabel} (${page.roleLabel ?? "unlabeled"})`} />
        </div>
    );
}

export default function DocumentDetailClient({ documentId }: { documentId: string }) {
    const [detail, setDetail] = useState<DocumentDetail | null>(null);
    const [loading, setLoading] = useState(true);
    const [notFound, setNotFound] = useState(false);
    const [error, setError] = useState<string | null>(null);

    useEffect(() => {
        let cancelled = false;
        setLoading(true);
        setNotFound(false);
        setError(null);
        fetch(`/api/documents/${documentId}`)
            .then(res => {
                if (res.status === 404) {
                    if (!cancelled) setNotFound(true);
                    return null;
                }
                if (!res.ok) throw new Error("Failed to fetch document");
                return res.json();
            })
            .then(data => {
                if (!cancelled && data) setDetail(data);
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
    }, [documentId]);

    const backLink = (
        <Link
            href="/dashboard/documents"
            className="inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground"
        >
            <ArrowLeft className="h-4 w-4" /> Back to documents
        </Link>
    );

    if (loading) {
        return (
            <div className="space-y-4">
                {backLink}
                <Card>
                    <CardContent className="py-12 text-center text-muted-foreground">Loading…</CardContent>
                </Card>
            </div>
        );
    }

    if (notFound) {
        return (
            <div className="space-y-4">
                {backLink}
                <Card>
                    <CardContent className="py-12 text-center text-muted-foreground">Document not found.</CardContent>
                </Card>
            </div>
        );
    }

    if (error || !detail) {
        return (
            <div className="space-y-4">
                {backLink}
                <Card>
                    <CardContent className="py-12 text-center text-red-500">
                        Error: {error ?? "Unknown error"}
                    </CardContent>
                </Card>
            </div>
        );
    }

    return (
        <div className="flex-1 space-y-4 overflow-auto">
            {backLink}

            {/* Header */}
            <Card>
                <CardHeader className="pb-3">
                    <CardTitle className="flex items-center gap-2 text-xl">
                        <FileText className="h-5 w-5" />
                        NF {detail.documentNumber}
                        <StatusBadge status={detail.status} />
                    </CardTitle>
                </CardHeader>
                <CardContent>
                    <div className="grid grid-cols-2 gap-x-6 gap-y-2 text-sm sm:grid-cols-3">
                        <Field label="Issuer" value={detail.issuerName ?? "—"} />
                        <Field label="CNPJ" value={detail.issuerCnpj} />
                        <Field label="Type" value={detail.documentType ?? "—"} />
                        <Field label="Total" value={formatCurrency(detail.totalValue)} />
                        <Field label="Sum entries" value={formatCurrency(detail.sumEntries)} />
                        <Field label="Linked entries" value={String(detail.entries.length)} />
                    </div>
                </CardContent>
            </Card>

            {/* Document image — the representative page (the fiscal document itself, not its
                boleto / payment proof), so it is clear which document this is. */}
            <Card>
                <CardHeader className="pb-3">
                    <CardTitle className="text-base">Document image</CardTitle>
                </CardHeader>
                <CardContent>
                    {(() => {
                        const hero = representativePage(detail.imageSources);
                        if (!hero) {
                            return (
                                <div className="flex h-24 flex-col items-center justify-center gap-1 rounded-md border border-dashed bg-muted/30 text-muted-foreground">
                                    <ImageOff className="h-5 w-5" />
                                    <span className="text-xs">No image available</span>
                                </div>
                            );
                        }
                        return (
                            <div className="space-y-2">
                                <div className="flex flex-wrap items-center gap-2 text-sm">
                                    <Badge variant="outline">{detail.documentType ?? "Document"}</Badge>
                                    <span className="text-muted-foreground">
                                        {detail.issuerName ?? detail.issuerCnpj}
                                    </span>
                                    {hero.roleLabel && (
                                        <span className="text-xs text-muted-foreground">· {hero.roleLabel}</span>
                                    )}
                                </div>
                                <div className="max-w-xl">
                                    <PageImageViewer
                                        src={hero.imageUrl}
                                        alt={`${detail.documentType ?? "Document"} image`}
                                    />
                                </div>
                            </div>
                        );
                    })()}
                </CardContent>
            </Card>

            {/* Source attachments — the full provenance bundle(s), every page labeled by its artifact
                role so the document page is distinguishable from its boleto / payment proof. */}
            {detail.imageSources.length > 0 && (
                <Card>
                    <CardHeader className="pb-3">
                        <CardTitle className="text-base">Source attachments ({detail.imageSources.length})</CardTitle>
                    </CardHeader>
                    <CardContent className="space-y-3">
                        {detail.imageSources.map(source => (
                            <div key={source.analysisId} className="space-y-2 rounded-md border p-3">
                                <div className="text-xs text-muted-foreground">
                                    From entry <span className="tabular-nums">{source.period}</span>
                                </div>
                                {source.pages.length === 0 ? (
                                    <div className="flex h-24 flex-col items-center justify-center gap-1 rounded-md border border-dashed bg-muted/30 text-muted-foreground">
                                        <ImageOff className="h-5 w-5" />
                                        <span className="text-xs">No image for this source</span>
                                    </div>
                                ) : (
                                    <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
                                        {source.pages.map(page => (
                                            <LabeledPage key={page.pageLabel} page={page} />
                                        ))}
                                    </div>
                                )}
                            </div>
                        ))}
                    </CardContent>
                </Card>
            )}

            {/* Linked entries */}
            <Card>
                <CardHeader className="pb-3">
                    <CardTitle className="text-base">Linked entries ({detail.entries.length})</CardTitle>
                </CardHeader>
                <CardContent>
                    {detail.entries.length === 0 ? (
                        <p className="py-6 text-center text-sm text-muted-foreground">No entries linked.</p>
                    ) : (
                        <div className="overflow-x-auto rounded-md border">
                            <div className="flex min-w-[720px] border-b bg-muted/50 text-xs font-medium text-muted-foreground">
                                <div className="w-[80px] shrink-0 px-3 py-2">Period</div>
                                <div className="w-[90px] shrink-0 px-3 py-2">Date</div>
                                <div className="flex-1 px-3 py-2">Description</div>
                                <div className="w-[140px] shrink-0 px-3 py-2">Category</div>
                                <div className="w-[140px] shrink-0 px-3 py-2">Vendor</div>
                                <div className="w-[60px] shrink-0 px-3 py-2">Unit</div>
                                <div className="w-[110px] shrink-0 px-3 py-2 text-right">Amount</div>
                                <div className="w-[70px] shrink-0 px-3 py-2 text-right">Open</div>
                            </div>
                            {detail.entries.map(e => (
                                <div
                                    key={e.entryId}
                                    className="flex min-w-[720px] items-center border-b border-border/50 text-sm hover:bg-muted/30"
                                >
                                    <div className="w-[80px] shrink-0 px-3 py-1.5 text-xs text-muted-foreground">
                                        {e.period}
                                    </div>
                                    <div className="w-[90px] shrink-0 px-3 py-1.5 text-xs tabular-nums">{e.date}</div>
                                    <div className="flex-1 px-3 py-1.5 truncate" title={e.description}>
                                        {e.description}
                                    </div>
                                    <div
                                        className="w-[140px] shrink-0 px-3 py-1.5 truncate text-xs"
                                        title={`${e.category ?? ""}${e.subcategory ? " / " + e.subcategory : ""}`}
                                    >
                                        {e.subcategory ?? e.category ?? "—"}
                                    </div>
                                    <div
                                        className="w-[140px] shrink-0 px-3 py-1.5 truncate text-xs"
                                        title={e.vendor ?? ""}
                                    >
                                        {e.vendor ?? "—"}
                                    </div>
                                    <div className="w-[60px] shrink-0 px-3 py-1.5 text-xs">{e.unitCode ?? "—"}</div>
                                    <div className="w-[110px] shrink-0 px-3 py-1.5 text-right tabular-nums">
                                        {formatCurrency(e.amount)}
                                    </div>
                                    <div className="w-[70px] shrink-0 px-3 py-1.5 flex justify-end">
                                        <Link
                                            href={entryHref(e.period, e.entryId)}
                                            className="inline-flex items-center gap-1 text-xs text-blue-600 hover:underline"
                                        >
                                            Open <ExternalLink className="h-3 w-3" />
                                        </Link>
                                    </div>
                                </div>
                            ))}
                        </div>
                    )}
                </CardContent>
            </Card>

            {/* Related documents */}
            <Card>
                <CardHeader className="pb-3">
                    <CardTitle className="text-base">Related documents ({detail.relatedDocuments.length})</CardTitle>
                </CardHeader>
                <CardContent>
                    {detail.relatedDocuments.length === 0 ? (
                        <p className="py-6 text-center text-sm text-muted-foreground">
                            No other documents are linked to these entries.
                        </p>
                    ) : (
                        <div className="overflow-x-auto rounded-md border">
                            <div className="flex min-w-[600px] border-b bg-muted/50 text-xs font-medium text-muted-foreground">
                                <div className="w-[140px] shrink-0 px-3 py-2">Number</div>
                                <div className="flex-1 px-3 py-2">Issuer</div>
                                <div className="w-[90px] shrink-0 px-3 py-2">Type</div>
                                <div className="w-[120px] shrink-0 px-3 py-2 text-right">Total</div>
                                <div className="w-[90px] shrink-0 px-3 py-2 text-right">Status</div>
                            </div>
                            {detail.relatedDocuments.map(r => (
                                <Link
                                    key={r.id}
                                    href={`/dashboard/documents/${r.id}`}
                                    className="flex min-w-[600px] items-center border-b border-border/50 text-sm hover:bg-muted/30"
                                >
                                    <div className="w-[140px] shrink-0 px-3 py-1.5 truncate font-medium tabular-nums">
                                        {r.documentNumber}
                                    </div>
                                    <div
                                        className="flex-1 px-3 py-1.5 truncate"
                                        title={`${r.issuerName ?? ""} (${r.issuerCnpj})`}
                                    >
                                        {r.issuerName ?? "—"}
                                    </div>
                                    <div className="w-[90px] shrink-0 px-3 py-1.5 truncate text-xs text-muted-foreground">
                                        {r.documentType ?? "—"}
                                    </div>
                                    <div className="w-[120px] shrink-0 px-3 py-1.5 text-right tabular-nums">
                                        {formatCurrency(r.totalValue)}
                                    </div>
                                    <div className="w-[90px] shrink-0 px-3 py-1.5 flex justify-end">
                                        <StatusBadge status={r.status} />
                                    </div>
                                </Link>
                            ))}
                        </div>
                    )}
                </CardContent>
            </Card>
        </div>
    );
}

function Field({ label, value }: { label: string; value: string }) {
    return (
        <div className="flex flex-col gap-0.5">
            <span className="text-[10px] uppercase tracking-wide text-muted-foreground">{label}</span>
            <span className="text-sm">{value}</span>
        </div>
    );
}
