"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { useVirtualizer } from "@tanstack/react-virtual";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { MultiSelect } from "@/components/ui/multi-select";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Receipt } from "lucide-react";

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
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);

    // Filters (now arrays for multi-select)
    const [selectedPeriods, setSelectedPeriods] = useState<string[]>([]);
    const [selectedCategories, setSelectedCategories] = useState<string[]>([]);
    const [selectedSubcategories, setSelectedSubcategories] = useState<string[]>([]);
    const [selectedMovementTypes, setSelectedMovementTypes] = useState<string[]>([]);
    const [search, setSearch] = useState("");

    useEffect(() => {
        fetch("/api/entries")
            .then(res => {
                if (!res.ok) throw new Error("Failed to fetch entries");
                return res.json();
            })
            .then(setEntries)
            .catch(e => setError(e.message))
            .finally(() => setLoading(false));
    }, []);

    // Derive filter options from data
    const periodOptions = useMemo(
        () =>
            [...new Set(entries.map(e => e.period))]
                .sort()
                .reverse()
                .map(v => ({ value: v, label: v })),
        [entries]
    );
    const categoryOptions = useMemo(
        () => [...new Set(entries.map(e => e.category))].sort().map(v => ({ value: v, label: v })),
        [entries]
    );
    const subcategoryOptions = useMemo(() => {
        const filtered =
            selectedCategories.length === 0 ? entries : entries.filter(e => selectedCategories.includes(e.category));
        return [...new Set(filtered.map(e => e.subcategory))].sort().map(v => ({ value: v, label: v }));
    }, [entries, selectedCategories]);

    const movementTypeOptions = [
        { value: "D", label: "Debit (D)" },
        { value: "C", label: "Credit (C)" },
    ];

    // Reset subcategories when categories change
    const handleCategoriesChange = (values: string[]) => {
        setSelectedCategories(values);
        // Remove any selected subcategories that no longer belong to selected categories
        if (values.length > 0) {
            const validSubs = new Set(entries.filter(e => values.includes(e.category)).map(e => e.subcategory));
            setSelectedSubcategories(prev => prev.filter(s => validSubs.has(s)));
        }
    };

    // Apply filters
    const filtered = useMemo(() => {
        const searchLower = search.toLowerCase();
        return entries.filter(e => {
            if (selectedPeriods.length > 0 && !selectedPeriods.includes(e.period)) return false;
            if (selectedCategories.length > 0 && !selectedCategories.includes(e.category)) return false;
            if (selectedSubcategories.length > 0 && !selectedSubcategories.includes(e.subcategory)) return false;
            if (selectedMovementTypes.length > 0 && !selectedMovementTypes.includes(e.movementType)) return false;
            if (searchLower && !e.description.toLowerCase().includes(searchLower)) return false;
            return true;
        });
    }, [entries, selectedPeriods, selectedCategories, selectedSubcategories, selectedMovementTypes, search]);

    // Totals
    const totals = useMemo(() => {
        let revenue = 0;
        let expenses = 0;
        for (const e of filtered) {
            if (e.movementType === "C") revenue += e.amount;
            else expenses += e.amount;
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

    if (loading) {
        return (
            <Card>
                <CardContent className="py-12 text-center text-muted-foreground">Loading entries...</CardContent>
            </Card>
        );
    }

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
                        <Receipt className="h-5 w-5" />
                        Entries
                    </CardTitle>
                </CardHeader>
                <CardContent className="space-y-4 flex-1 flex flex-col min-h-0">
                    {/* Filters */}
                    <div className="flex flex-wrap gap-3 items-end">
                        <div className="w-[160px]">
                            <label className="block text-xs text-muted-foreground mb-1">Period</label>
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
                        <div className="flex-1 min-w-[200px]">
                            <label className="block text-xs text-muted-foreground mb-1">Search</label>
                            <Input
                                placeholder="Search description..."
                                value={search}
                                onChange={e => setSearch(e.target.value)}
                                className="h-9"
                            />
                        </div>
                    </div>

                    {/* Summary */}
                    <div className="flex items-center gap-4 text-sm">
                        <span className="text-muted-foreground">{filtered.length} entries</span>
                        <Badge variant="outline" className="text-green-700 border-green-300">
                            Revenue: {formatCurrency(totals.revenue)}
                        </Badge>
                        <Badge variant="outline" className="text-red-700 border-red-300">
                            Expenses: {formatCurrency(totals.expenses)}
                        </Badge>
                        <Badge variant={totals.net >= 0 ? "secondary" : "destructive"}>
                            Net: {formatCurrency(totals.net)}
                        </Badge>
                    </div>

                    {/* Table */}
                    <div className="rounded-md border flex-1 flex flex-col min-h-0">
                        {/* Header */}
                        <div className="flex bg-muted/50 text-xs font-medium text-muted-foreground border-b shrink-0">
                            <div className="w-[80px] px-3 py-2 shrink-0">Period</div>
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
                                            <div className="w-[80px] px-3 shrink-0 text-muted-foreground text-xs">
                                                {entry.period}
                                            </div>
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
                    </div>
                </CardContent>
            </Card>
        </div>
    );
}
