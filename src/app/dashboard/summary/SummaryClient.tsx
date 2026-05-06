"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { useVirtualizer } from "@tanstack/react-virtual";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { MultiSelect } from "@/components/ui/multi-select";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { BarChart3, ChevronRight, X } from "lucide-react";
import { cn } from "@/lib/utils";

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
    // Category → subcategory tree
    const categoryTree = useMemo(() => {
        const map = new Map<string, string[]>();
        for (const r of data) {
            if (!map.has(r.category)) map.set(r.category, []);
            const subs = map.get(r.category)!;
            if (!subs.includes(r.subcategory)) subs.push(r.subcategory);
        }
        return [...map.entries()]
            .sort(([a], [b]) => a.localeCompare(b))
            .map(([cat, subs]) => ({ category: cat, subcategories: subs.sort() }));
    }, [data]);

    // Derive available years from periods
    const years = useMemo(() => [...new Set(data.map(r => r.period.slice(0, 4)))].sort().reverse(), [data]);
    const allPeriods = useMemo(() => [...new Set(data.map(r => r.period))], [data]);

    const selectYear = (year: string) => {
        const yearPeriods = allPeriods.filter(p => p.startsWith(year));
        setSelectedPeriods(yearPeriods);
    };

    const movementTypeOptions = [
        { value: "D", label: "Debit (D)" },
        { value: "C", label: "Credit (C)" },
    ];

    // Collapsed state for categories
    const [collapsedCategories, setCollapsedCategories] = useState<Set<string>>(new Set());

    const toggleCollapse = (cat: string) => {
        setCollapsedCategories(prev => {
            const next = new Set(prev);
            if (next.has(cat)) next.delete(cat);
            else next.add(cat);
            return next;
        });
    };

    // Toggle category: selects/deselects all its subcategories
    const toggleCategory = (cat: string) => {
        const node = categoryTree.find(n => n.category === cat);
        if (!node) return;
        const allSelected = node.subcategories.every(s => selectedSubcategories.includes(s));
        if (allSelected) {
            // Deselect all subcategories of this category
            setSelectedSubcategories(prev => prev.filter(s => !node.subcategories.includes(s)));
        } else {
            // Select all subcategories of this category
            setSelectedSubcategories(prev => [...new Set([...prev, ...node.subcategories])]);
        }
    };

    const toggleSubcategory = (sub: string) => {
        setSelectedSubcategories(prev => (prev.includes(sub) ? prev.filter(s => s !== sub) : [...prev, sub]));
    };

    // Filter
    const filtered = useMemo(() => {
        return data
            .filter(r => {
                if (selectedPeriods.length > 0 && !selectedPeriods.includes(r.period)) return false;
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
    }, [data, selectedPeriods, selectedSubcategories, selectedMovementTypes]);

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

                {/* Type */}
                <Card>
                    <CardContent className="p-3 space-y-2">
                        <span className="text-xs font-medium text-muted-foreground">Type</span>
                        <MultiSelect
                            options={movementTypeOptions}
                            selected={selectedMovementTypes}
                            onSelectedChange={setSelectedMovementTypes}
                            placeholder="All"
                            className="w-full"
                        />
                    </CardContent>
                </Card>

                {/* Category / Subcategory tree */}
                <Card className="flex-1 flex flex-col min-h-0">
                    <CardContent className="p-3 flex flex-col min-h-0 gap-1">
                        <div className="flex items-center justify-between mb-1">
                            <span className="text-xs font-medium text-muted-foreground">
                                Categories / Subcategories
                            </span>
                            {selectedSubcategories.length > 0 && (
                                <button
                                    onClick={() => setSelectedSubcategories([])}
                                    className="text-xs text-muted-foreground hover:text-foreground"
                                >
                                    <X className="h-3 w-3" />
                                </button>
                            )}
                        </div>
                        <div className="overflow-auto flex-1 min-h-0">
                            {categoryTree.map(({ category, subcategories }) => {
                                const allSelected = subcategories.every(s => selectedSubcategories.includes(s));
                                const someSelected = subcategories.some(s => selectedSubcategories.includes(s));
                                const collapsed = collapsedCategories.has(category);
                                return (
                                    <div key={category} className="mb-0.5">
                                        <div className="flex items-center gap-0.5">
                                            <button
                                                onClick={() => toggleCollapse(category)}
                                                className="p-0.5 text-muted-foreground hover:text-foreground"
                                            >
                                                <ChevronRight
                                                    className={cn(
                                                        "h-3 w-3 transition-transform",
                                                        !collapsed && "rotate-90"
                                                    )}
                                                />
                                            </button>
                                            <button
                                                onClick={() => toggleCategory(category)}
                                                className={cn(
                                                    "flex-1 text-left px-1.5 py-1 rounded text-xs truncate transition-colors font-medium",
                                                    allSelected
                                                        ? "bg-primary text-primary-foreground"
                                                        : someSelected
                                                          ? "bg-primary/20 text-primary"
                                                          : "hover:bg-muted"
                                                )}
                                                title={category}
                                            >
                                                {category}
                                            </button>
                                        </div>
                                        {!collapsed && (
                                            <div className="ml-4 space-y-0.5 mt-0.5">
                                                {subcategories.map(sub => (
                                                    <button
                                                        key={sub}
                                                        onClick={() => toggleSubcategory(sub)}
                                                        className={cn(
                                                            "w-full text-left px-1.5 py-0.5 rounded text-xs truncate transition-colors",
                                                            selectedSubcategories.includes(sub)
                                                                ? "bg-primary text-primary-foreground"
                                                                : "hover:bg-muted text-muted-foreground"
                                                        )}
                                                        title={sub}
                                                    >
                                                        {sub}
                                                    </button>
                                                ))}
                                            </div>
                                        )}
                                    </div>
                                );
                            })}
                        </div>
                    </CardContent>
                </Card>
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
