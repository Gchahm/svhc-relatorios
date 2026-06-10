"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import Link from "next/link";
import { useVirtualizer } from "@tanstack/react-virtual";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { FileText, ExternalLink } from "lucide-react";
import type { DocumentStatus } from "@/lib/documents";

interface DocumentRow {
    id: string;
    documentNumber: string;
    issuerCnpj: string;
    issuerName: string | null;
    documentType: string | null;
    totalValue: number | null;
    linkedCount: number;
    sumEntries: number;
    status: DocumentStatus;
}

interface LinkedEntry {
    entryId: string;
    period: string;
    date: string;
    description: string;
    amount: number;
    sourceAttachmentId: string | null;
}

interface DocumentDetail extends Omit<DocumentRow, "linkedCount"> {
    entries: LinkedEntry[];
}

function formatCurrency(value: number | null): string {
    if (value === null) return "—";
    return value.toLocaleString("pt-BR", { style: "currency", currency: "BRL" });
}

/** Deep link to the entries page focused on one entry (feature 018). */
function entryHref(period: string, entryId: string): string {
    return `/dashboard/entries?period=${encodeURIComponent(period)}&entry=${encodeURIComponent(entryId)}`;
}

function StatusBadge({ status }: { status: DocumentStatus }) {
    if (status === "over") return <Badge variant="destructive">over</Badge>;
    if (status === "within") {
        return (
            <Badge variant="outline" className="border-green-400 text-green-700">
                within
            </Badge>
        );
    }
    if (status === "under") {
        return (
            <Badge variant="outline" className="border-yellow-400 text-yellow-700">
                under
            </Badge>
        );
    }
    return <Badge variant="secondary">unknown</Badge>;
}

export default function DocumentsClient() {
    const [data, setData] = useState<DocumentRow[]>([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);

    const [typeFilter, setTypeFilter] = useState<string>("all");
    const [search, setSearch] = useState("");

    const [detail, setDetail] = useState<DocumentDetail | null>(null);
    const [detailLoading, setDetailLoading] = useState(false);

    useEffect(() => {
        fetch("/api/documents")
            .then(res => {
                if (!res.ok) throw new Error("Failed to fetch documents");
                return res.json();
            })
            .then(setData)
            .catch(e => setError(e.message))
            .finally(() => setLoading(false));
    }, []);

    const typeOptions = useMemo(
        () => [...new Set(data.map(r => r.documentType).filter((t): t is string => !!t))].sort(),
        [data]
    );

    const filtered = useMemo(() => {
        const q = search.trim().toLowerCase();
        return data.filter(r => {
            if (typeFilter !== "all" && r.documentType !== typeFilter) return false;
            if (q) {
                const hay = `${r.documentNumber} ${r.issuerName ?? ""} ${r.issuerCnpj}`.toLowerCase();
                if (!hay.includes(q)) return false;
            }
            return true;
        });
    }, [data, typeFilter, search]);

    const openDetail = (id: string) => {
        setDetailLoading(true);
        setDetail(null);
        fetch(`/api/documents/${id}`)
            .then(res => {
                if (!res.ok) throw new Error("Failed to fetch document");
                return res.json();
            })
            .then(setDetail)
            .catch(e => setError(e.message))
            .finally(() => setDetailLoading(false));
    };

    const parentRef = useRef<HTMLDivElement>(null);
    const virtualizer = useVirtualizer({
        count: filtered.length,
        getScrollElement: () => parentRef.current,
        estimateSize: () => 40,
        overscan: 20,
    });

    if (error) {
        return (
            <Card>
                <CardContent className="py-12 text-center text-red-500">Error: {error}</CardContent>
            </Card>
        );
    }

    return (
        <div className="flex-1 flex flex-col min-h-0">
            <Card className="flex-1 flex flex-col min-h-0">
                <CardHeader className="pb-3">
                    <CardTitle className="flex items-center gap-2 text-xl">
                        <FileText className="h-5 w-5" />
                        Documents (Notas Fiscais)
                    </CardTitle>
                </CardHeader>
                <CardContent className="space-y-4 flex-1 flex flex-col min-h-0">
                    {/* Filters */}
                    <div className="flex flex-wrap gap-3 items-end">
                        <div className="w-[200px]">
                            <label className="block text-xs text-muted-foreground mb-1">Type</label>
                            <Select value={typeFilter} onValueChange={setTypeFilter}>
                                <SelectTrigger className="w-full">
                                    <SelectValue placeholder="All types" />
                                </SelectTrigger>
                                <SelectContent>
                                    <SelectItem value="all">All types</SelectItem>
                                    {typeOptions.map(t => (
                                        <SelectItem key={t} value={t}>
                                            {t}
                                        </SelectItem>
                                    ))}
                                </SelectContent>
                            </Select>
                        </div>
                        <div className="w-[260px]">
                            <label className="block text-xs text-muted-foreground mb-1">Search (number / issuer)</label>
                            <Input
                                value={search}
                                onChange={e => setSearch(e.target.value)}
                                placeholder="NF number or issuer…"
                            />
                        </div>
                    </div>

                    {/* Summary */}
                    <div className="flex items-center gap-3 text-sm">
                        <span className="text-muted-foreground">
                            {loading ? "Loading..." : `${filtered.length} documents`}
                        </span>
                    </div>

                    {/* Table */}
                    <div className="rounded-md border flex-1 flex flex-col min-h-0">
                        <div className="flex bg-muted/50 text-xs font-medium text-muted-foreground border-b shrink-0">
                            <div className="w-[140px] px-3 py-2 shrink-0">Number</div>
                            <div className="flex-1 px-3 py-2 min-w-0">Issuer</div>
                            <div className="w-[90px] px-3 py-2 shrink-0">Type</div>
                            <div className="w-[120px] px-3 py-2 shrink-0 text-right">Total</div>
                            <div className="w-[120px] px-3 py-2 shrink-0 text-right">Sum entries</div>
                            <div className="w-[70px] px-3 py-2 shrink-0 text-right">Links</div>
                            <div className="w-[90px] px-3 py-2 shrink-0 text-right">Status</div>
                        </div>

                        <div ref={parentRef} className="flex-1 overflow-auto min-h-0">
                            {filtered.length === 0 && !loading ? (
                                <div className="py-12 text-center text-sm text-muted-foreground">
                                    No documents found.
                                </div>
                            ) : (
                                <div
                                    style={{
                                        height: `${virtualizer.getTotalSize()}px`,
                                        width: "100%",
                                        position: "relative",
                                    }}
                                >
                                    {virtualizer.getVirtualItems().map(virtualRow => {
                                        const row = filtered[virtualRow.index];
                                        return (
                                            <div
                                                key={row.id}
                                                className="flex items-center border-b border-border/50 hover:bg-muted/30 text-sm absolute w-full cursor-pointer"
                                                style={{
                                                    height: `${virtualRow.size}px`,
                                                    transform: `translateY(${virtualRow.start}px)`,
                                                }}
                                                onClick={() => openDetail(row.id)}
                                                title="Click to view linked entries"
                                            >
                                                <div
                                                    className="w-[140px] px-3 shrink-0 truncate font-medium tabular-nums"
                                                    title={row.documentNumber}
                                                >
                                                    {row.documentNumber}
                                                </div>
                                                <div
                                                    className="flex-1 px-3 min-w-0 truncate"
                                                    title={`${row.issuerName ?? ""} (${row.issuerCnpj})`}
                                                >
                                                    {row.issuerName ?? <span className="text-muted-foreground">—</span>}
                                                </div>
                                                <div className="w-[90px] px-3 shrink-0 truncate text-muted-foreground text-xs">
                                                    {row.documentType ?? "—"}
                                                </div>
                                                <div className="w-[120px] px-3 shrink-0 text-right tabular-nums">
                                                    {formatCurrency(row.totalValue)}
                                                </div>
                                                <div className="w-[120px] px-3 shrink-0 text-right tabular-nums">
                                                    {formatCurrency(row.sumEntries)}
                                                </div>
                                                <div className="w-[70px] px-3 shrink-0 text-right tabular-nums text-muted-foreground">
                                                    {row.linkedCount}
                                                </div>
                                                <div className="w-[90px] px-3 shrink-0 flex justify-end">
                                                    <StatusBadge status={row.status} />
                                                </div>
                                            </div>
                                        );
                                    })}
                                </div>
                            )}
                        </div>
                    </div>
                </CardContent>
            </Card>

            {/* Detail dialog: a document's linked entries, each deep-linking to the entries view. */}
            <Dialog open={detailLoading || detail !== null} onOpenChange={open => !open && setDetail(null)}>
                <DialogContent className="max-w-2xl">
                    <DialogHeader>
                        <DialogTitle className="flex items-center gap-2">
                            <FileText className="h-4 w-4" />
                            {detail ? `NF ${detail.documentNumber}` : "Loading…"}
                        </DialogTitle>
                    </DialogHeader>
                    {detail && (
                        <div className="space-y-3">
                            <div className="flex flex-wrap gap-x-6 gap-y-1 text-sm">
                                <span>
                                    <span className="text-muted-foreground">Issuer:</span> {detail.issuerName ?? "—"} (
                                    {detail.issuerCnpj})
                                </span>
                                <span>
                                    <span className="text-muted-foreground">Type:</span> {detail.documentType ?? "—"}
                                </span>
                                <span>
                                    <span className="text-muted-foreground">Total:</span>{" "}
                                    {formatCurrency(detail.totalValue)}
                                </span>
                                <span>
                                    <span className="text-muted-foreground">Sum entries:</span>{" "}
                                    {formatCurrency(detail.sumEntries)}
                                </span>
                                <StatusBadge status={detail.status} />
                            </div>

                            <div className="rounded-md border max-h-80 overflow-auto">
                                <div className="flex bg-muted/50 text-xs font-medium text-muted-foreground border-b sticky top-0">
                                    <div className="w-[80px] px-3 py-2 shrink-0">Period</div>
                                    <div className="w-[90px] px-3 py-2 shrink-0">Date</div>
                                    <div className="flex-1 px-3 py-2 min-w-0">Description</div>
                                    <div className="w-[110px] px-3 py-2 shrink-0 text-right">Amount</div>
                                    <div className="w-[70px] px-3 py-2 shrink-0 text-right">Open</div>
                                </div>
                                {detail.entries.map(e => (
                                    <div
                                        key={e.entryId}
                                        className="flex items-center border-b border-border/50 text-sm hover:bg-muted/30"
                                    >
                                        <div className="w-[80px] px-3 py-1.5 shrink-0 text-muted-foreground text-xs">
                                            {e.period}
                                        </div>
                                        <div className="w-[90px] px-3 py-1.5 shrink-0 text-xs tabular-nums">
                                            {e.date}
                                        </div>
                                        <div className="flex-1 px-3 py-1.5 min-w-0 truncate" title={e.description}>
                                            {e.description}
                                        </div>
                                        <div className="w-[110px] px-3 py-1.5 shrink-0 text-right tabular-nums">
                                            {formatCurrency(e.amount)}
                                        </div>
                                        <div className="w-[70px] px-3 py-1.5 shrink-0 flex justify-end">
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
                        </div>
                    )}
                </DialogContent>
            </Dialog>
        </div>
    );
}
