"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { useVirtualizer } from "@tanstack/react-virtual";
import { Badge } from "@/components/ui/badge";
import { MultiSelect } from "@/components/ui/multi-select";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { SortableHeader, useSort } from "@/components/filters/SortableHeader";
import { FileSearch } from "lucide-react";

interface DocAnalysisRow {
    id: string;
    documentId: string;
    analyzedAt: number;
    documentType: string | null;
    extractedAmount: number | null;
    amountMatch: boolean | null;
    extractedCnpj: string | null;
    issuerName: string | null;
    vendorMatch: boolean | null;
    extractedDate: string | null;
    dateMatch: boolean | null;
    documentNumber: string | null;
    serviceDescription: string | null;
    error: string | null;
    entryDate: string;
    entryDescription: string;
    entryAmount: number;
    entryMovementType: string;
    vendorName: string | null;
    subcategoryName: string | null;
    categoryName: string | null;
}

function MatchBadge({ match, label }: { match: boolean | null; label?: string }) {
    if (match === null) return <span className="text-muted-foreground text-xs">—</span>;
    if (match) {
        return (
            <Badge variant="outline" className="border-green-400 text-green-700 text-[10px] px-1.5 py-0">
                {label || "OK"}
            </Badge>
        );
    }
    return (
        <Badge variant="destructive" className="text-[10px] px-1.5 py-0">
            {label || "MISMATCH"}
        </Badge>
    );
}

function formatCurrency(value: number) {
    return value.toLocaleString("pt-BR", { style: "currency", currency: "BRL" });
}

export default function DocumentAnalysesClient() {
    const [data, setData] = useState<DocAnalysisRow[]>([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);

    const [selectedDocTypes, setSelectedDocTypes] = useState<string[]>([]);
    const [selectedMatchStatus, setSelectedMatchStatus] = useState<string[]>([]);

    useEffect(() => {
        fetch("/api/document-analyses")
            .then(res => {
                if (!res.ok) throw new Error("Failed to fetch");
                return res.json();
            })
            .then(setData)
            .catch(e => setError(e.message))
            .finally(() => setLoading(false));
    }, []);

    const { sortKey, sortDir, toggleSort, sortFn } = useSort<DocAnalysisRow>("entryAmount", "desc");

    const docTypeOptions = useMemo(
        () => [...new Set(data.map(r => r.documentType).filter(Boolean))].sort().map(v => ({ value: v!, label: v! })),
        [data]
    );

    const matchStatusOptions = [
        { value: "all_match", label: "All match" },
        { value: "has_mismatch", label: "Has mismatch" },
        { value: "has_error", label: "Has error" },
    ];

    const filtered = useMemo(() => {
        const result = data.filter(r => {
            if (selectedDocTypes.length > 0 && !selectedDocTypes.includes(r.documentType || "")) return false;
            if (selectedMatchStatus.length > 0) {
                const allMatch = r.amountMatch !== false && r.vendorMatch !== false && r.dateMatch !== false;
                const hasMismatch = r.amountMatch === false || r.vendorMatch === false || r.dateMatch === false;
                const hasError = !!r.error;

                const passes = selectedMatchStatus.some(s => {
                    if (s === "all_match") return allMatch && !hasError;
                    if (s === "has_mismatch") return hasMismatch;
                    if (s === "has_error") return hasError;
                    return false;
                });
                if (!passes) return false;
            }
            return true;
        });
        return sortFn(result, {
            entryDate: r => r.entryDate,
            entryDescription: r => r.entryDescription.toLowerCase(),
            entryAmount: r => r.entryAmount,
            extractedAmount: r => r.extractedAmount ?? 0,
            documentType: r => r.documentType || "",
            vendorName: r => r.vendorName || "",
        });
    }, [data, selectedDocTypes, selectedMatchStatus, sortFn]);

    const summary = useMemo(() => {
        const analyzed = data.filter(r => !r.error);
        return {
            total: data.length,
            errors: data.length - analyzed.length,
            amountOk: analyzed.filter(r => r.amountMatch === true).length,
            amountBad: analyzed.filter(r => r.amountMatch === false).length,
            vendorOk: analyzed.filter(r => r.vendorMatch === true).length,
            vendorBad: analyzed.filter(r => r.vendorMatch === false).length,
            dateOk: analyzed.filter(r => r.dateMatch === true).length,
            dateBad: analyzed.filter(r => r.dateMatch === false).length,
        };
    }, [data]);

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
                        <FileSearch className="h-5 w-5" />
                        Document Analyses
                    </CardTitle>
                </CardHeader>
                <CardContent className="space-y-4 flex-1 flex flex-col min-h-0">
                    {/* Summary */}
                    <div className="flex items-center gap-3 text-sm flex-wrap">
                        <span className="text-muted-foreground">
                            {loading ? "Loading..." : `${filtered.length} analyses`}
                        </span>
                        {!loading && (
                            <>
                                {summary.amountBad > 0 && (
                                    <Badge variant="destructive">{summary.amountBad} amount mismatch</Badge>
                                )}
                                {summary.vendorBad > 0 && (
                                    <Badge variant="destructive">{summary.vendorBad} vendor mismatch</Badge>
                                )}
                                {summary.dateBad > 0 && (
                                    <Badge variant="outline" className="border-yellow-400 text-yellow-700">
                                        {summary.dateBad} date mismatch
                                    </Badge>
                                )}
                                {summary.errors > 0 && <Badge variant="secondary">{summary.errors} errors</Badge>}
                            </>
                        )}
                    </div>

                    {/* Filters */}
                    <div className="flex flex-wrap gap-3 items-end">
                        <div className="w-[160px]">
                            <label className="block text-xs text-muted-foreground mb-1">Document Type</label>
                            <MultiSelect
                                options={docTypeOptions}
                                selected={selectedDocTypes}
                                onSelectedChange={setSelectedDocTypes}
                                placeholder="All"
                                className="w-full"
                            />
                        </div>
                        <div className="w-[160px]">
                            <label className="block text-xs text-muted-foreground mb-1">Match Status</label>
                            <MultiSelect
                                options={matchStatusOptions}
                                selected={selectedMatchStatus}
                                onSelectedChange={setSelectedMatchStatus}
                                placeholder="All"
                                className="w-full"
                            />
                        </div>
                    </div>

                    {/* Table */}
                    <div className="rounded-md border flex-1 flex flex-col min-h-0">
                        <div className="flex bg-muted/50 text-xs font-medium text-muted-foreground border-b shrink-0">
                            <div className="w-[80px] px-3 py-2 shrink-0">
                                <SortableHeader
                                    label="Date"
                                    sortKey="entryDate"
                                    currentSort={sortKey}
                                    currentDirection={sortDir}
                                    onSort={toggleSort}
                                />
                            </div>
                            <div className="flex-1 px-3 py-2 min-w-0">ID</div>
                            <div className="w-[100px] px-3 py-2 shrink-0">
                                <SortableHeader
                                    label="Vendor"
                                    sortKey="vendorName"
                                    currentSort={sortKey}
                                    currentDirection={sortDir}
                                    onSort={toggleSort}
                                />
                            </div>
                            <div className="w-[80px] px-3 py-2 shrink-0">
                                <SortableHeader
                                    label="Type"
                                    sortKey="documentType"
                                    currentSort={sortKey}
                                    currentDirection={sortDir}
                                    onSort={toggleSort}
                                />
                            </div>
                            <div className="w-[100px] px-3 py-2 shrink-0 flex justify-end">
                                <SortableHeader
                                    label="Entry Amt"
                                    sortKey="entryAmount"
                                    currentSort={sortKey}
                                    currentDirection={sortDir}
                                    onSort={toggleSort}
                                />
                            </div>
                            <div className="w-[100px] px-3 py-2 shrink-0 flex justify-end">
                                <SortableHeader
                                    label="Doc Amt"
                                    sortKey="extractedAmount"
                                    currentSort={sortKey}
                                    currentDirection={sortDir}
                                    onSort={toggleSort}
                                />
                            </div>
                            <div className="w-[60px] px-3 py-2 shrink-0 text-center">Amt</div>
                            <div className="w-[60px] px-3 py-2 shrink-0 text-center">Vendor</div>
                            <div className="w-[60px] px-3 py-2 shrink-0 text-center">Date</div>
                        </div>

                        <div ref={parentRef} className="flex-1 overflow-auto min-h-0">
                            {filtered.length === 0 && !loading ? (
                                <div className="py-12 text-center text-sm text-muted-foreground">
                                    No document analyses found.
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
                                                className="flex items-center border-b border-border/50 hover:bg-muted/30 text-sm absolute w-full"
                                                style={{
                                                    height: `${virtualRow.size}px`,
                                                    transform: `translateY(${virtualRow.start}px)`,
                                                }}
                                                title={row.serviceDescription || row.error || ""}
                                            >
                                                <div className="w-[80px] px-3 shrink-0 text-muted-foreground text-xs">
                                                    {row.entryDate}
                                                </div>
                                                <div className="flex-1 px-3 min-w-0 text-xs font-mono text-muted-foreground">
                                                    {row.id}
                                                </div>
                                                <div
                                                    className="w-[100px] px-3 shrink-0 truncate text-xs text-muted-foreground"
                                                    title={row.vendorName || ""}
                                                >
                                                    {row.vendorName || "—"}
                                                </div>
                                                <div className="w-[80px] px-3 shrink-0 text-xs text-muted-foreground">
                                                    {row.documentType || (row.error ? "error" : "—")}
                                                </div>
                                                <div className="w-[100px] px-3 shrink-0 text-right tabular-nums text-xs">
                                                    {formatCurrency(row.entryAmount)}
                                                </div>
                                                <div className="w-[100px] px-3 shrink-0 text-right tabular-nums text-xs">
                                                    {row.extractedAmount != null
                                                        ? formatCurrency(row.extractedAmount)
                                                        : "—"}
                                                </div>
                                                <div className="w-[60px] px-3 shrink-0 flex justify-center">
                                                    <MatchBadge match={row.amountMatch} />
                                                </div>
                                                <div className="w-[60px] px-3 shrink-0 flex justify-center">
                                                    <MatchBadge match={row.vendorMatch} />
                                                </div>
                                                <div className="w-[60px] px-3 shrink-0 flex justify-center">
                                                    <MatchBadge match={row.dateMatch} />
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
