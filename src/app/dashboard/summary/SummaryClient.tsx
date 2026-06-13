"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { useVirtualizer } from "@tanstack/react-virtual";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { MultiSelect } from "@/components/ui/multi-select";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { CategoryTree } from "@/components/filters/CategoryTree";
import { SortableHeader, useSort } from "@/components/filters/SortableHeader";
import { BarChart3, X } from "lucide-react";
import { useTranslation, useLocale } from "@/lib/i18n/client";
import { formatCurrency } from "@/lib/i18n/formatters.client";
import { plural } from "@/lib/i18n/plural";

interface SummaryRow {
    period: string;
    category: string;
    subcategory: string;
    movementType: string;
    total: number;
    count: number;
}

export default function SummaryClient() {
    const t = useTranslation();
    const locale = useLocale();
    const [data, setData] = useState<SummaryRow[]>([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);

    // Filters
    const [selectedPeriods, setSelectedPeriods] = useState<string[]>([]);
    const [selectedSubcategories, setSelectedSubcategories] = useState<string[]>([]);

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
            return true;
        });
        return sortFn(result, {
            period: r => r.period,
            category: r => r.category,
            subcategory: r => r.subcategory,
            total: r => r.total,
            count: r => r.count,
        });
    }, [data, selectedPeriods, selectedSubcategories, sortFn]);

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
                <CardContent className="py-12 text-center text-red-500 dark:text-red-400">
                    {t("error.generic_prefix")}: {error}
                </CardContent>
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
                            <span className="text-xs font-medium text-muted-foreground">{t("filter.periods")}</span>
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
                            placeholder={t("form.all_periods")}
                            className="w-full"
                        />
                    </CardContent>
                </Card>

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
                            {t("page.summary_title")}
                        </CardTitle>
                        <div className="flex items-center gap-4 text-sm">
                            <span className="text-muted-foreground">
                                {loading
                                    ? t("form.loading")
                                    : `${filtered.length} ${plural(t, "count.rows", filtered.length)}`}
                            </span>
                            {!loading && (
                                <>
                                    <Badge
                                        variant="outline"
                                        className="text-green-700 dark:text-green-400 border-green-300 dark:border-green-800"
                                    >
                                        {t("summary.revenue")}: {formatCurrency(totals.revenue, locale)}
                                    </Badge>
                                    <Badge
                                        variant="outline"
                                        className="text-red-700 dark:text-red-400 border-red-300 dark:border-red-800"
                                    >
                                        {t("summary.expenses")}: {formatCurrency(totals.expenses, locale)}
                                    </Badge>
                                    <Badge variant={totals.net >= 0 ? "secondary" : "destructive"}>
                                        {t("summary.net")}: {formatCurrency(totals.net, locale)}
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
                                    label={t("table.period")}
                                    sortKey="period"
                                    currentSort={sortKey}
                                    currentDirection={sortDir}
                                    onSort={toggleSort}
                                />
                            </div>
                            <div className="w-[160px] px-3 py-2 shrink-0">
                                <SortableHeader
                                    label={t("table.category")}
                                    sortKey="category"
                                    currentSort={sortKey}
                                    currentDirection={sortDir}
                                    onSort={toggleSort}
                                />
                            </div>
                            <div className="flex-1 px-3 py-2 min-w-0">
                                <SortableHeader
                                    label={t("table.subcategory")}
                                    sortKey="subcategory"
                                    currentSort={sortKey}
                                    currentDirection={sortDir}
                                    onSort={toggleSort}
                                />
                            </div>
                            <div className="w-[120px] px-3 py-2 shrink-0 flex justify-end">
                                <SortableHeader
                                    label={t("table.total")}
                                    sortKey="total"
                                    currentSort={sortKey}
                                    currentDirection={sortDir}
                                    onSort={toggleSort}
                                />
                            </div>
                            <div className="w-[70px] px-3 py-2 shrink-0 flex justify-end">
                                <SortableHeader
                                    label={t("table.entries")}
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
                                            <div
                                                className={`w-[120px] px-3 shrink-0 text-right tabular-nums ${
                                                    row.movementType === "D"
                                                        ? "text-red-600 dark:text-red-400"
                                                        : "text-green-600 dark:text-green-400"
                                                }`}
                                            >
                                                {formatCurrency(row.total, locale)}
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
                                <div className="flex-1 px-3 py-2 min-w-0 text-xs text-muted-foreground">
                                    {t("summary.total")}
                                </div>
                                <div className="w-[120px] px-3 py-2 shrink-0 text-right tabular-nums font-semibold">
                                    {formatCurrency(totals.net, locale)}
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
