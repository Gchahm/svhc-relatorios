"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useVirtualizer } from "@tanstack/react-virtual";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { MultiSelect } from "@/components/ui/multi-select";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { ChevronRight, Receipt, X } from "lucide-react";
import { cn } from "@/lib/utils";

interface Entry {
    id: number;
    date: string;
    description: string;
    amount: number;
    movementType: string;
    sourceUrl: string;
    period: string;
    category: string;
    subcategory: string;
    vendor: string | null;
    unitCode: string | null;
}

function getCurrentPeriod(): string {
    const now = new Date();
    return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, "0")}`;
}

function formatCurrency(value: number): string {
    return value.toLocaleString("pt-BR", { style: "currency", currency: "BRL" });
}

function formatDate(iso: string): string {
    const [y, m, d] = iso.split("-");
    return `${d}/${m}/${y}`;
}

function stripDescriptionPrefix(description: string, subcategory: string): string {
    let text = description.replace(/^BLOCO [A-Z], N° \d+ - RECEBIMENTO\s*/i, "");
    text = text.replace(/^[\s\-]+/, "");
    if (text.includes(" - ")) {
        const [before, ...rest] = text.split(" - ");
        const normalize = (s: string) =>
            s
                .normalize("NFD")
                .replace(/[\u0300-\u036f]/g, "")
                .trim()
                .toUpperCase();
        if (normalize(before) === normalize(subcategory)) {
            text = rest.join(" - ").trim();
        }
    }
    return text;
}

export default function EntriesClient() {
    const [entries, setEntries] = useState<Entry[]>([]);
    const [periods, setPeriods] = useState<string[]>([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);

    // Filters
    const [selectedPeriod, setSelectedPeriod] = useState(getCurrentPeriod());
    const [selectedSubcategories, setSelectedSubcategories] = useState<string[]>([]);
    const [selectedMovementTypes, setSelectedMovementTypes] = useState<string[]>([]);
    const [search, setSearch] = useState("");
    const [expandedCategories, setExpandedCategories] = useState<Set<string>>(new Set());

    // Fetch available periods
    useEffect(() => {
        fetch("/api/periods")
            .then(res => {
                if (!res.ok) throw new Error("Failed to fetch periods");
                return res.json();
            })
            .then((data: string[]) => {
                setPeriods(data);
                if (data.length > 0 && !data.includes(selectedPeriod)) {
                    setSelectedPeriod(data[0]);
                }
            })
            .catch(e => setError(e.message));
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, []);

    // Fetch entries when period changes
    const fetchEntries = useCallback((period: string) => {
        setLoading(true);
        setError(null);
        fetch(`/api/entries?period=${encodeURIComponent(period)}`)
            .then(res => {
                if (!res.ok) throw new Error("Failed to fetch entries");
                return res.json();
            })
            .then(setEntries)
            .catch(e => setError(e.message))
            .finally(() => setLoading(false));
    }, []);

    useEffect(() => {
        if (selectedPeriod) {
            fetchEntries(selectedPeriod);
        }
    }, [selectedPeriod, fetchEntries]);

    // Category → subcategory tree
    const categoryTree = useMemo(() => {
        const map = new Map<string, string[]>();
        for (const e of entries) {
            if (!map.has(e.category)) map.set(e.category, []);
            const subs = map.get(e.category)!;
            if (!subs.includes(e.subcategory)) subs.push(e.subcategory);
        }
        return [...map.entries()]
            .sort(([a], [b]) => a.localeCompare(b))
            .map(([cat, subs]) => ({ category: cat, subcategories: subs.sort() }));
    }, [entries]);

    const movementTypeOptions = [
        { value: "D", label: "Debit (D)" },
        { value: "C", label: "Credit (C)" },
    ];

    const toggleCollapse = (cat: string) => {
        setExpandedCategories(prev => {
            const next = new Set(prev);
            if (next.has(cat)) next.delete(cat);
            else next.add(cat);
            return next;
        });
    };

    const toggleCategory = (cat: string) => {
        const node = categoryTree.find(n => n.category === cat);
        if (!node) return;
        const allSelected = node.subcategories.every(s => selectedSubcategories.includes(s));
        if (allSelected) {
            setSelectedSubcategories(prev => prev.filter(s => !node.subcategories.includes(s)));
        } else {
            setSelectedSubcategories(prev => [...new Set([...prev, ...node.subcategories])]);
        }
    };

    const toggleSubcategory = (sub: string) => {
        setSelectedSubcategories(prev => (prev.includes(sub) ? prev.filter(s => s !== sub) : [...prev, sub]));
    };

    // Reset client-side filters when period changes
    const handlePeriodChange = (value: string) => {
        setSelectedPeriod(value);
        setSelectedSubcategories([]);
        setSelectedMovementTypes([]);
        setSearch("");
    };

    // Apply client-side filters
    const filtered = useMemo(() => {
        const searchLower = search.toLowerCase();
        return entries.filter(e => {
            if (selectedSubcategories.length > 0 && !selectedSubcategories.includes(e.subcategory)) return false;
            if (selectedMovementTypes.length > 0 && !selectedMovementTypes.includes(e.movementType)) return false;
            if (searchLower && !e.description.toLowerCase().includes(searchLower)) return false;
            return true;
        });
    }, [entries, selectedSubcategories, selectedMovementTypes, search]);

    // Totals
    const totals = useMemo(() => {
        let revenue = 0;
        let expenses = 0;
        for (const e of filtered) {
            if (e.movementType === "C") revenue += e.amount;
            else expenses += e.amount;
        }
        return { revenue, expenses, net: revenue - expenses, count: filtered.length };
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
                {/* Period */}
                <Card>
                    <CardContent className="p-3 space-y-2">
                        <span className="text-xs font-medium text-muted-foreground">Period</span>
                        <Select value={selectedPeriod} onValueChange={handlePeriodChange}>
                            <SelectTrigger className="h-9">
                                <SelectValue placeholder="Select period" />
                            </SelectTrigger>
                            <SelectContent>
                                {periods.map(p => (
                                    <SelectItem key={p} value={p}>
                                        {p}
                                    </SelectItem>
                                ))}
                            </SelectContent>
                        </Select>
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

                {/* Search */}
                <Card>
                    <CardContent className="p-3 space-y-2">
                        <span className="text-xs font-medium text-muted-foreground">Search</span>
                        <Input
                            placeholder="Search description..."
                            value={search}
                            onChange={e => setSearch(e.target.value)}
                            className="h-9"
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
                                const collapsed = !expandedCategories.has(category);
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
                            <Receipt className="h-5 w-5" />
                            Entries
                        </CardTitle>
                        <div className="flex items-center gap-4 text-sm">
                            <span className="text-muted-foreground">
                                {loading ? "Loading..." : `${filtered.length} entries`}
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
                        {/* Header */}
                        <div className="flex bg-muted/50 text-xs font-medium text-muted-foreground border-b shrink-0">
                            <div className="w-[90px] px-3 py-2 shrink-0">Date</div>
                            <div className="flex-1 px-3 py-2 min-w-0">Description</div>
                            <div className="w-[140px] px-3 py-2 shrink-0">Category</div>
                            <div className="w-[140px] px-3 py-2 shrink-0">Subcategory</div>
                            <div className="w-[120px] px-3 py-2 shrink-0 text-right">Amount</div>
                            <div className="w-[40px] px-3 py-2 shrink-0 text-center">Type</div>
                        </div>

                        {/* Virtualized body */}
                        <div ref={parentRef} className="flex-1 overflow-auto min-h-0">
                            <div
                                style={{
                                    height: `${virtualizer.getTotalSize()}px`,
                                    width: "100%",
                                    position: "relative",
                                }}
                            >
                                {virtualizer.getVirtualItems().map(virtualRow => {
                                    const entry = filtered[virtualRow.index];
                                    return (
                                        <div
                                            key={entry.id}
                                            className="flex items-center border-b border-border/50 hover:bg-muted/30 text-sm absolute w-full"
                                            style={{
                                                height: `${virtualRow.size}px`,
                                                transform: `translateY(${virtualRow.start}px)`,
                                            }}
                                        >
                                            <div className="w-[90px] px-3 shrink-0 whitespace-nowrap">
                                                {formatDate(entry.date)}
                                            </div>
                                            <div className="flex-1 px-3 min-w-0 truncate" title={entry.description}>
                                                {stripDescriptionPrefix(entry.description, entry.subcategory)}
                                            </div>
                                            <div
                                                className="w-[140px] px-3 shrink-0 text-muted-foreground truncate text-xs"
                                                title={entry.category}
                                            >
                                                {entry.category}
                                            </div>
                                            <div
                                                className="w-[140px] px-3 shrink-0 text-muted-foreground truncate text-xs"
                                                title={entry.subcategory}
                                            >
                                                {entry.subcategory}
                                            </div>
                                            <div
                                                className={`w-[120px] px-3 shrink-0 text-right tabular-nums ${
                                                    entry.movementType === "D" ? "text-red-600" : "text-green-600"
                                                }`}
                                            >
                                                {formatCurrency(entry.amount)}
                                            </div>
                                            <div className="w-[40px] px-3 shrink-0 text-center text-muted-foreground text-xs">
                                                {entry.movementType}
                                            </div>
                                        </div>
                                    );
                                })}
                            </div>
                        </div>

                        {/* Footer */}
                        {!loading && filtered.length > 0 && (
                            <div className="flex items-center border-t bg-muted/50 text-sm font-medium shrink-0">
                                <div className="w-[90px] px-3 py-2 shrink-0" />
                                <div className="flex-1 px-3 py-2 min-w-0 text-xs text-muted-foreground">Total</div>
                                <div className="w-[140px] px-3 py-2 shrink-0" />
                                <div className="w-[140px] px-3 py-2 shrink-0" />
                                <div className="w-[120px] px-3 py-2 shrink-0 text-right tabular-nums font-semibold">
                                    {formatCurrency(totals.net)}
                                </div>
                                <div className="w-[40px] px-3 py-2 shrink-0 text-center text-xs text-muted-foreground">
                                    {totals.count}
                                </div>
                            </div>
                        )}
                    </div>
                </CardContent>
            </Card>
        </div>
    );
}
