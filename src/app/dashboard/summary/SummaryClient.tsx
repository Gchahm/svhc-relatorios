"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { useVirtualizer } from "@tanstack/react-virtual";
import { Badge } from "@/components/ui/badge";
import { MultiSelect } from "@/components/ui/multi-select";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { BarChart3 } from "lucide-react";

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
    const [selectedCategories, setSelectedCategories] = useState<string[]>([]);
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
    const categoryOptions = useMemo(
        () => [...new Set(data.map(r => r.category))].sort().map(v => ({ value: v, label: v })),
        [data]
    );
    const subcategoryOptions = useMemo(() => {
        const filtered =
            selectedCategories.length === 0 ? data : data.filter(r => selectedCategories.includes(r.category));
        return [...new Set(filtered.map(r => r.subcategory))].sort().map(v => ({ value: v, label: v }));
    }, [data, selectedCategories]);

    const movementTypeOptions = [
        { value: "D", label: "Debit (D)" },
        { value: "C", label: "Credit (C)" },
    ];

    // Reset subcategories when categories change
    const handleCategoriesChange = (values: string[]) => {
        setSelectedCategories(values);
        if (values.length > 0) {
            const validSubs = new Set(data.filter(r => values.includes(r.category)).map(r => r.subcategory));
            setSelectedSubcategories(prev => prev.filter(s => validSubs.has(s)));
        }
    };

    // Filter
    const filtered = useMemo(() => {
        return data
            .filter(r => {
                if (selectedPeriods.length > 0 && !selectedPeriods.includes(r.period)) return false;
                if (selectedCategories.length > 0 && !selectedCategories.includes(r.category)) return false;
                if (selectedSubcategories.length > 0 && !selectedSubcategories.includes(r.subcategory)) return false;
                if (selectedMovementTypes.length > 0 && !selectedMovementTypes.includes(r.movementType)) return false;
                return true;
            })
            .sort((a, b) => {
                const periodCmp = b.period.localeCompare(a.period);
                if (periodCmp !== 0) return periodCmp;
                const catCmp = a.category.localeCompare(b.category);
                if (catCmp !== 0) return catCmp;
                return a.subcategory.localeCompare(b.subcategory);
            });
    }, [data, selectedPeriods, selectedCategories, selectedSubcategories, selectedMovementTypes]);

    // Totals
    const totals = useMemo(() => {
        let revenue = 0;
        let expenses = 0;
        for (const r of filtered) {
            if (r.movementType === "C") revenue += r.total;
            else expenses += r.total;
        }
        return { revenue, expenses, net: revenue - expenses };
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
        <div className="flex-1 flex flex-col min-h-0">
            <Card className="flex-1 flex flex-col min-h-0">
                <CardHeader className="pb-3">
                    <CardTitle className="flex items-center gap-2 text-xl">
                        <BarChart3 className="h-5 w-5" />
                        Summary by Subcategory
                    </CardTitle>
                </CardHeader>
                <CardContent className="space-y-4 flex-1 flex flex-col min-h-0">
                    {/* Filters */}
                    <div className="flex flex-wrap gap-3 items-end">
                        <div className="w-[200px]">
                            <label className="block text-xs text-muted-foreground mb-1">Periods</label>
                            <MultiSelect
                                options={periodOptions}
                                selected={selectedPeriods}
                                onSelectedChange={setSelectedPeriods}
                                placeholder="All"
                                className="w-full"
                            />
                        </div>
                        <div className="w-[200px]">
                            <label className="block text-xs text-muted-foreground mb-1">Category</label>
                            <MultiSelect
                                options={categoryOptions}
                                selected={selectedCategories}
                                onSelectedChange={handleCategoriesChange}
                                placeholder="All"
                                className="w-full"
                            />
                        </div>
                        <div className="w-[200px]">
                            <label className="block text-xs text-muted-foreground mb-1">Subcategory</label>
                            <MultiSelect
                                options={subcategoryOptions}
                                selected={selectedSubcategories}
                                onSelectedChange={setSelectedSubcategories}
                                placeholder="All"
                                className="w-full"
                            />
                        </div>
                        <div className="w-[160px]">
                            <label className="block text-xs text-muted-foreground mb-1">Type</label>
                            <MultiSelect
                                options={movementTypeOptions}
                                selected={selectedMovementTypes}
                                onSelectedChange={setSelectedMovementTypes}
                                placeholder="All"
                                className="w-full"
                            />
                        </div>
                    </div>

                    {/* Summary */}
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

                    {/* Table */}
                    <div className="rounded-md border flex-1 flex flex-col min-h-0">
                        <div className="flex bg-muted/50 text-xs font-medium text-muted-foreground border-b shrink-0">
                            <div className="w-[80px] px-3 py-2 shrink-0">Period</div>
                            <div className="w-[160px] px-3 py-2 shrink-0">Category</div>
                            <div className="flex-1 px-3 py-2 min-w-0">Subcategory</div>
                            <div className="w-[40px] px-3 py-2 shrink-0 text-center">Type</div>
                            <div className="w-[120px] px-3 py-2 shrink-0 text-right">Total</div>
                            <div className="w-[70px] px-3 py-2 shrink-0 text-right">Entries</div>
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
                    </div>
                </CardContent>
            </Card>
        </div>
    );
}
