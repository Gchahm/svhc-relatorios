"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
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

interface ImageSource {
    attachmentId: string;
    analysisId: string;
    entryId: string;
    period: string;
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

interface PageInfo {
    pageIndex: number;
    pageLabel: string;
    ext: string;
    imageUrl: string;
}

function formatCurrency(value: number | null): string {
    if (value === null) return "—";
    return value.toLocaleString("pt-BR", { style: "currency", currency: "BRL" });
}

/** Deep link to the entries page focused on one entry (feature 018). */
function entryHref(period: string, entryId: string): string {
    return `/dashboard/entries?period=${encodeURIComponent(period)}&entry=${encodeURIComponent(entryId)}`;
}

/** Loads and renders the page images for one provenance attachment (by its analysis id). */
function SourceImages({ source }: { source: ImageSource }) {
    const [pages, setPages] = useState<PageInfo[]>([]);
    const [done, setDone] = useState(false);

    useEffect(() => {
        let cancelled = false;
        setPages([]);
        setDone(false);
        // A pages-list failure is non-fatal: it simply yields no gallery (FR-009).
        fetch(`/api/attachment-analyses/${source.analysisId}/pages`)
            .then(res => (res.ok ? res.json() : []))
            .then((data: PageInfo[]) => {
                if (!cancelled) setPages(Array.isArray(data) ? data : []);
            })
            .catch(() => {
                if (!cancelled) setPages([]);
            })
            .finally(() => {
                if (!cancelled) setDone(true);
            });
        return () => {
            cancelled = true;
        };
    }, [source.analysisId]);

    return (
        <div className="space-y-2 rounded-md border p-3">
            <div className="text-xs text-muted-foreground">
                From entry <span className="tabular-nums">{source.period}</span>
            </div>
            {done && pages.length === 0 ? (
                <div className="flex h-24 flex-col items-center justify-center gap-1 rounded-md border border-dashed bg-muted/30 text-muted-foreground">
                    <ImageOff className="h-5 w-5" />
                    <span className="text-xs">No image for this source</span>
                </div>
            ) : (
                <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
                    {pages.map(page => (
                        <PageImageViewer key={page.pageLabel} src={page.imageUrl} alt={`Page ${page.pageLabel}`} />
                    ))}
                </div>
            )}
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

            {/* Document image(s) */}
            <Card>
                <CardHeader className="pb-3">
                    <CardTitle className="text-base">Document image</CardTitle>
                </CardHeader>
                <CardContent>
                    {detail.imageSources.length === 0 ? (
                        <div className="flex h-24 flex-col items-center justify-center gap-1 rounded-md border border-dashed bg-muted/30 text-muted-foreground">
                            <ImageOff className="h-5 w-5" />
                            <span className="text-xs">No image available</span>
                        </div>
                    ) : (
                        <div className="space-y-3">
                            {detail.imageSources.map(source => (
                                <SourceImages key={source.analysisId} source={source} />
                            ))}
                        </div>
                    )}
                </CardContent>
            </Card>

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
