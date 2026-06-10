"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { useVirtualizer } from "@tanstack/react-virtual";
import { Input } from "@/components/ui/input";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { FileText } from "lucide-react";
import type { DocumentStatus } from "@/lib/documents";
import { StatusBadge } from "./StatusBadge";

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

function formatCurrency(value: number | null): string {
    if (value === null) return "—";
    return value.toLocaleString("pt-BR", { style: "currency", currency: "BRL" });
}

export default function DocumentsClient() {
    const router = useRouter();
    const [data, setData] = useState<DocumentRow[]>([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);

    const [typeFilter, setTypeFilter] = useState<string>("all");
    const [search, setSearch] = useState("");

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
                                                onClick={() => router.push(`/dashboard/documents/${row.id}`)}
                                                title="Click to open the document detail page"
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
        </div>
    );
}
