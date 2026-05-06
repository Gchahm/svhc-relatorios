"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { useVirtualizer } from "@tanstack/react-virtual";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { MultiSelect } from "@/components/ui/multi-select";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { CategoryTree } from "@/components/filters/CategoryTree";
import { TypeFilter } from "@/components/filters/TypeFilter";
import { SortableHeader, useSort } from "@/components/filters/SortableHeader";
import { BarChart3, X } from "lucide-react";

interface SummaryRow {
    period: string;
    category: string;
    subcategory: string;
    movementType: string;
    total: number;
    count: number;
}

function formatCurrency(value: number): string {
    return value.toLocaleString("pt-BR", { style: "currency", currency: "BRL" });
}

export default function SummaryClient() {
    const [data, setData] = useState<SummaryRow[]>([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);

    // Filters
    const [selectedPeriods, setSelectedPeriods] = useState<string[]>([]);
    const [selectedSubcategories, setSelectedSubcategories] = useState<string[]>([]);
    const [selectedMovementTypes, setSelectedMovementTypes] = useState<string[]>([]);

    useEffect(() => {
        fetch("/api/summary")
            .then(res => {
                if (!res.ok) throw new Error("Failed to fetch summary");
                return res.json();
            })
            .then(setData)
            .catch(e => setError(e.message))
            .finally(() => setLoading(false));
    }, []);

    // Derive filter options
    const periodOptions = useMemo(
        () =>
            [...new Set(data.map(r => r.period))]
                .sort()
                .reverse()
                .map(v => ({ value: v, label: v })),
        [data]
    );

    // Derive available years from periods
    const years = useMemo(() => [...new Set(data.map(r => r.period.slice(0, 4)))].sort().reverse(), [data]);
    const allPeriods = useMemo(() => [...new Set(data.map(r => r.period))], [data]);

    const selectYear = (year: string) => {
        const yearPeriods = allPeriods.filter(p => p.startsWith(year));
        setSelectedPeriods(yearPeriods);
    };

    // Sorting
    const { sortKey, sortDir, toggleSort, sortFn } = useSort<SummaryRow>("period", "desc");

    // Filter + sort
    const filtered = useMemo(() => {
        const result = data.filter(r => {
            if (selectedPeriods.length > 0 && !selectedPeriods.includes(r.period)) return false;
            if (selectedSubcategories.length > 0 && !selectedSubcategories.includes(r.subcategory)) return false;
            if (selectedMovementTypes.length > 0 && !selectedMovementTypes.includes(r.movementType)) return false;
            return true;
        });
        return sortFn(result, {
            period: r => r.period,
            category: r => r.category,
            subcategory: r => r.subcategory,
            movementType: r => r.movementType,
            total: r => r.total,
            count: r => r.count,
        });
    }, [data, selectedPeriods, selectedSubcategories, selectedMovementTypes, sortFn]);

    // Totals
    const totals = useMemo(() => {
        let revenue = 0;
        let expenses = 0;
        let totalEntries = 0;
        for (const r of filtered) {
            if (r.movementType === "C") revenue += r.total;
            else expenses += r.total;
            totalEntries += r.count;
        }
        return { revenue, expenses, net: revenue - expenses, totalEntries };
    }, [filtered]);

    // Virtualizer
    const parentRef = useRef<HTMLDivElement>(null);
    const virtualizer = useVirtualizer({
        count: filtered.length,
        getScrollElement: () => parentRef.current,
        estimateSize: () => 36,
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
        <div className="flex-1 flex gap-4 min-h-0">
            {/* Sidebar filters */}
            <div className="w-[220px] shrink-0 flex flex-col gap-3 overflow-auto min-h-0">
                {/* Periods */}
                <Card>
                    <CardContent className="p-3 space-y-2">
                        <div className="flex items-center justify-between">
                            <span className="text-xs font-medium text-muted-foreground">Periods</span>
                            {selectedPeriods.length > 0 && (
                                <button
                                    onClick={() => setSelectedPeriods([])}
                                    className="text-xs text-muted-foreground hover:text-foreground"
                                >
                                    <X className="h-3 w-3" />
                                </button>
                            )}
                        </div>
                        <div className="flex flex-wrap gap-1">
                            {years.map(year => (
                                <Button
                                    key={year}
                                    variant={
                                        selectedPeriods.length > 0 && selectedPeriods.every(p => p.startsWith(year))
                                            ? "default"
                                            : "outline"
                                    }
                                    size="sm"
                                    className="h-7 px-2 text-xs"
                                    onClick={() => selectYear(year)}
                                >
                                    {year}
                                </Button>
                            ))}
                        </div>
                        <MultiSelect
                            options={periodOptions}
                            selected={selectedPeriods}
                            onSelectedChange={setSelectedPeriods}
                            placeholder="All periods"
                            className="w-full"
                        />
                    </CardContent>
                </Card>

                <TypeFilter selected={selectedMovementTypes} onSelectedChange={setSelectedMovementTypes} />

                <CategoryTree
                    data={data}
                    selected={selectedSubcategories}
                    onSelectedChange={setSelectedSubcategories}
                />
            </div>

            {/* Main content */}
            <Card className="flex-1 flex flex-col min-h-0">
                <CardHeader className="pb-3">
                    <div className="flex items-center justify-between">
                        <CardTitle className="flex items-center gap-2 text-xl">
                            <BarChart3 className="h-5 w-5" />
                            Summary by Subcategory
                        </CardTitle>
                        <div className="flex items-center gap-4 text-sm">
                            <span className="text-muted-foreground">
                                {loading ? "Loading..." : `${filtered.length} rows`}
                            </span>
                            {!loading && (
                                <>
                                    <Badge variant="outline" className="text-green-700 border-green-300">
                                        Revenue: {formatCurrency(totals.revenue)}
                                    </Badge>
                                    <Badge variant="outline" className="text-red-700 border-red-300">
                                        Expenses: {formatCurrency(totals.expenses)}
                                    </Badge>
                                    <Badge variant={totals.net >= 0 ? "secondary" : "destructive"}>
                                        Net: {formatCurrency(totals.net)}
                                    </Badge>
                                </>
                            )}
                        </div>
                    </div>
                </CardHeader>
                <CardContent className="flex-1 flex flex-col min-h-0 pt-0">
                    <div className="rounded-md border flex-1 flex flex-col min-h-0">
                        <div className="flex bg-muted/50 text-xs font-medium text-muted-foreground border-b shrink-0">
                            <div className="w-[80px] px-3 py-2 shrink-0">
                                <SortableHeader
                                    label="Period"
                                    sortKey="period"
                                    currentSort={sortKey}
                                    currentDirection={sortDir}
                                    onSort={toggleSort}
                                />
                            </div>
                            <div className="w-[160px] px-3 py-2 shrink-0">
                                <SortableHeader
                                    label="Category"
                                    sortKey="category"
                                    currentSort={sortKey}
                                    currentDirection={sortDir}
                                    onSort={toggleSort}
                                />
                            </div>
                            <div className="flex-1 px-3 py-2 min-w-0">
                                <SortableHeader
                                    label="Subcategory"
                                    sortKey="subcategory"
                                    currentSort={sortKey}
                                    currentDirection={sortDir}
                                    onSort={toggleSort}
                                />
                            </div>
                            <div className="w-[40px] px-3 py-2 shrink-0 flex justify-center">
                                <SortableHeader
                                    label="Type"
                                    sortKey="movementType"
                                    currentSort={sortKey}
                                    currentDirection={sortDir}
                                    onSort={toggleSort}
                                />
                            </div>
                            <div className="w-[120px] px-3 py-2 shrink-0 flex justify-end">
                                <SortableHeader
                                    label="Total"
                                    sortKey="total"
                                    currentSort={sortKey}
                                    currentDirection={sortDir}
                                    onSort={toggleSort}
                                />
                            </div>
                            <div className="w-[70px] px-3 py-2 shrink-0 flex justify-end">
                                <SortableHeader
                                    label="Entries"
                                    sortKey="count"
                                    currentSort={sortKey}
                                    currentDirection={sortDir}
                                    onSort={toggleSort}
                                />
                            </div>
                        </div>

                        <div ref={parentRef} className="flex-1 overflow-auto min-h-0">
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
                                            key={`${row.period}-${row.category}-${row.subcategory}-${row.movementType}`}
                                            className="flex items-center border-b border-border/50 hover:bg-muted/30 text-sm absolute w-full"
                                            style={{
                                                height: `${virtualRow.size}px`,
                                                transform: `translateY(${virtualRow.start}px)`,
                                            }}
                                        >
                                            <div className="w-[80px] px-3 shrink-0 text-muted-foreground text-xs">
                                                {row.period}
                                            </div>
                                            <div
                                                className="w-[160px] px-3 shrink-0 text-muted-foreground truncate text-xs"
                                                title={row.category}
                                            >
                                                {row.category}
                                            </div>
                                            <div className="flex-1 px-3 min-w-0 truncate" title={row.subcategory}>
                                                {row.subcategory}
                                            </div>
                                            <div className="w-[40px] px-3 shrink-0 text-center text-muted-foreground text-xs">
                                                {row.movementType}
                                            </div>
                                            <div
                                                className={`w-[120px] px-3 shrink-0 text-right tabular-nums ${
                                                    row.movementType === "D" ? "text-red-600" : "text-green-600"
                                                }`}
                                            >
                                                {formatCurrency(row.total)}
                                            </div>
                                            <div className="w-[70px] px-3 shrink-0 text-right tabular-nums text-muted-foreground">
                                                {row.count}
                                            </div>
                                        </div>
                                    );
                                })}
                            </div>
                        </div>

                        {/* Footer */}
                        {!loading && filtered.length > 0 && (
                            <div className="flex items-center border-t bg-muted/50 text-sm font-medium shrink-0">
                                <div className="w-[80px] px-3 py-2 shrink-0" />
                                <div className="w-[160px] px-3 py-2 shrink-0" />
                                <div className="flex-1 px-3 py-2 min-w-0 text-xs text-muted-foreground">Total</div>
                                <div className="w-[40px] px-3 py-2 shrink-0" />
                                <div className="w-[120px] px-3 py-2 shrink-0 text-right tabular-nums font-semibold">
                                    {formatCurrency(totals.net)}
                                </div>
                                <div className="w-[70px] px-3 py-2 shrink-0 text-right tabular-nums text-muted-foreground">
                                    {totals.totalEntries}
                                </div>
                            </div>
                        )}
                    </div>
                </CardContent>
            </Card>
        </div>
    );
}
