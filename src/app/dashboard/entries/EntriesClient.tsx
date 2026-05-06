"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useVirtualizer } from "@tanstack/react-virtual";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { CategoryTree } from "@/components/filters/CategoryTree";
import { TypeFilter } from "@/components/filters/TypeFilter";
import { SortableHeader, useSort } from "@/components/filters/SortableHeader";
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

    // Reset client-side filters when period changes
    const handlePeriodChange = (value: string) => {
        setSelectedPeriod(value);
        setSelectedSubcategories([]);
        setSelectedMovementTypes([]);
        setSearch("");
    };

    // Sorting
    const { sortKey, sortDir, toggleSort, sortFn } = useSort<Entry>("date", "asc");

    // Apply client-side filters + sort
    const filtered = useMemo(() => {
        const searchLower = search.toLowerCase();
        const result = entries.filter(e => {
            if (selectedSubcategories.length > 0 && !selectedSubcategories.includes(e.subcategory)) return false;
            if (selectedMovementTypes.length > 0 && !selectedMovementTypes.includes(e.movementType)) return false;
            if (searchLower && !e.description.toLowerCase().includes(searchLower)) return false;
            return true;
        });
        return sortFn(result, {
            date: e => e.date,
            description: e => e.description.toLowerCase(),
            category: e => e.category,
            subcategory: e => e.subcategory,
            amount: e => e.amount,
            movementType: e => e.movementType,
        });
    }, [entries, selectedSubcategories, selectedMovementTypes, search, sortFn]);

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

                <TypeFilter selected={selectedMovementTypes} onSelectedChange={setSelectedMovementTypes} />

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

                <CategoryTree
                    data={entries}
                    selected={selectedSubcategories}
                    onSelectedChange={setSelectedSubcategories}
                />
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
                        <div className="flex bg-muted/50 text-xs font-medium text-muted-foreground border-b shrink-0">
                            <div className="w-[90px] px-3 py-2 shrink-0">
                                <SortableHeader
                                    label="Date"
                                    sortKey="date"
                                    currentSort={sortKey}
                                    currentDirection={sortDir}
                                    onSort={toggleSort}
                                />
                            </div>
                            <div className="flex-1 px-3 py-2 min-w-0">
                                <SortableHeader
                                    label="Description"
                                    sortKey="description"
                                    currentSort={sortKey}
                                    currentDirection={sortDir}
                                    onSort={toggleSort}
                                />
                            </div>
                            <div className="w-[140px] px-3 py-2 shrink-0">
                                <SortableHeader
                                    label="Category"
                                    sortKey="category"
                                    currentSort={sortKey}
                                    currentDirection={sortDir}
                                    onSort={toggleSort}
                                />
                            </div>
                            <div className="w-[140px] px-3 py-2 shrink-0">
                                <SortableHeader
                                    label="Subcategory"
                                    sortKey="subcategory"
                                    currentSort={sortKey}
                                    currentDirection={sortDir}
                                    onSort={toggleSort}
                                />
                            </div>
                            <div className="w-[120px] px-3 py-2 shrink-0 flex justify-end">
                                <SortableHeader
                                    label="Amount"
                                    sortKey="amount"
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
