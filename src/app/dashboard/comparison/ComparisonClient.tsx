"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { useVirtualizer } from "@tanstack/react-virtual";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Badge } from "@/components/ui/badge";
import { ArrowLeftRight } from "lucide-react";
import { useTranslation, useLocale } from "@/lib/i18n/client";
import { formatCurrency, formatNumber } from "@/lib/i18n/formatters.client";
import { plural } from "@/lib/i18n/plural";
import type { SupportedLocale } from "@/lib/i18n/catalog";

interface ComparisonRow {
    category: string;
    subcategory: string;
    movementType: string;
    valueP1: number;
    valueP2: number;
    diff: number;
    pctChange: number | null;
}

function formatPct(value: number | null, locale: SupportedLocale): string {
    if (value === null) return "—";
    // `pctChange` is already a percentage magnitude (e.g. 12.5 → "12,5%"); keep the explicit sign
    // and use the shared locale-aware number formatter for the digits (1 decimal).
    return `${value >= 0 ? "+" : ""}${formatNumber(value, 1, locale)}%`;
}

function isDiffPositive(row: ComparisonRow): boolean {
    // For expenses (D), a decrease (negative diff) is good -> green
    // For revenue (C), an increase (positive diff) is good -> green
    if (row.movementType === "D") return row.diff < 0;
    return row.diff > 0;
}

export default function ComparisonClient() {
    const t = useTranslation();
    const locale = useLocale();
    const [periods, setPeriods] = useState<string[]>([]);
    const [period1, setPeriod1] = useState<string>("");
    const [period2, setPeriod2] = useState<string>("");
    const [data, setData] = useState<ComparisonRow[]>([]);
    const [loading, setLoading] = useState(false);
    const [periodsLoading, setPeriodsLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);

    // Fetch available periods and default to latest two
    useEffect(() => {
        fetch("/api/periods")
            .then(res => {
                if (!res.ok) throw new Error("Failed to fetch periods");
                return res.json();
            })
            .then((data: string[]) => {
                setPeriods(data);
                if (data.length >= 2) {
                    setPeriod1(data[1]);
                    setPeriod2(data[0]);
                } else if (data.length === 1) {
                    setPeriod1(data[0]);
                    setPeriod2(data[0]);
                }
            })
            .catch(e => setError(e.message))
            .finally(() => setPeriodsLoading(false));
    }, []);

    // Fetch comparison data whenever both periods are set
    useEffect(() => {
        if (!period1 || !period2) return;
        setLoading(true);
        setError(null);
        fetch(`/api/comparison?p1=${encodeURIComponent(period1)}&p2=${encodeURIComponent(period2)}`)
            .then(res => {
                if (!res.ok) throw new Error("Failed to fetch comparison data");
                return res.json();
            })
            .then(setData)
            .catch(e => setError(e.message))
            .finally(() => setLoading(false));
    }, [period1, period2]);

    // Totals
    const totals = useMemo(() => {
        let revenueP1 = 0,
            revenueP2 = 0,
            expensesP1 = 0,
            expensesP2 = 0;
        for (const row of data) {
            if (row.movementType === "C") {
                revenueP1 += row.valueP1;
                revenueP2 += row.valueP2;
            } else {
                expensesP1 += row.valueP1;
                expensesP2 += row.valueP2;
            }
        }
        return { revenueP1, revenueP2, expensesP1, expensesP2 };
    }, [data]);

    // Virtualizer
    const parentRef = useRef<HTMLDivElement>(null);
    const virtualizer = useVirtualizer({
        count: data.length,
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
        <div className="flex-1 flex flex-col min-h-0">
            <Card className="flex-1 flex flex-col min-h-0">
                <CardHeader className="pb-3">
                    <CardTitle className="flex items-center gap-2 text-xl">
                        <ArrowLeftRight className="h-5 w-5" />
                        {t("page.comparison_title")}
                    </CardTitle>
                </CardHeader>
                <CardContent className="space-y-4 flex-1 flex flex-col min-h-0">
                    {/* Period selectors */}
                    <div className="flex flex-wrap gap-3 items-end">
                        <div className="w-[160px]">
                            <label className="block text-xs text-muted-foreground mb-1">{t("table.period_base")}</label>
                            <Select value={period1} onValueChange={setPeriod1} disabled={periodsLoading}>
                                <SelectTrigger className="h-9">
                                    <SelectValue placeholder={t("form.select_placeholder")} />
                                </SelectTrigger>
                                <SelectContent>
                                    {periods.map(p => (
                                        <SelectItem key={p} value={p}>
                                            {p}
                                        </SelectItem>
                                    ))}
                                </SelectContent>
                            </Select>
                        </div>
                        <div className="flex items-center pb-1 text-muted-foreground">
                            <ArrowLeftRight className="h-4 w-4" />
                        </div>
                        <div className="w-[160px]">
                            <label className="block text-xs text-muted-foreground mb-1">
                                {t("table.period_compare")}
                            </label>
                            <Select value={period2} onValueChange={setPeriod2} disabled={periodsLoading}>
                                <SelectTrigger className="h-9">
                                    <SelectValue placeholder={t("form.select_placeholder")} />
                                </SelectTrigger>
                                <SelectContent>
                                    {periods.map(p => (
                                        <SelectItem key={p} value={p}>
                                            {p}
                                        </SelectItem>
                                    ))}
                                </SelectContent>
                            </Select>
                        </div>
                    </div>

                    {/* Summary badges */}
                    <div className="flex items-center gap-4 text-sm flex-wrap">
                        <span className="text-muted-foreground">
                            {loading
                                ? t("form.loading")
                                : `${data.length} ${plural(t, "count.subcategories", data.length)}`}
                        </span>
                        {!loading && data.length > 0 && (
                            <>
                                <Badge
                                    variant="outline"
                                    className="text-green-700 dark:text-green-400 border-green-300 dark:border-green-800"
                                >
                                    {t("summary.revenue")}: {formatCurrency(totals.revenueP1, locale)} →{" "}
                                    {formatCurrency(totals.revenueP2, locale)}
                                </Badge>
                                <Badge
                                    variant="outline"
                                    className="text-red-700 dark:text-red-400 border-red-300 dark:border-red-800"
                                >
                                    {t("summary.expenses")}: {formatCurrency(totals.expensesP1, locale)} →{" "}
                                    {formatCurrency(totals.expensesP2, locale)}
                                </Badge>
                            </>
                        )}
                    </div>

                    {/* Table */}
                    <div className="rounded-md border flex-1 flex flex-col min-h-0">
                        {/* Header */}
                        <div className="flex bg-muted/50 text-xs font-medium text-muted-foreground border-b shrink-0">
                            <div className="w-[140px] px-3 py-2 shrink-0">{t("table.category")}</div>
                            <div className="flex-1 px-3 py-2 min-w-0">{t("table.subcategory")}</div>
                            <div className="w-[40px] px-3 py-2 shrink-0 text-center">{t("table.movement")}</div>
                            <div className="w-[130px] px-3 py-2 shrink-0 text-right">
                                {period1 || t("table.period")}
                            </div>
                            <div className="w-[130px] px-3 py-2 shrink-0 text-right">
                                {period2 || t("table.period")}
                            </div>
                            <div className="w-[120px] px-3 py-2 shrink-0 text-right">{t("table.difference")}</div>
                            <div className="w-[80px] px-3 py-2 shrink-0 text-right">{t("table.pct_change")}</div>
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
                                    const row = data[virtualRow.index];
                                    const positive = isDiffPositive(row);
                                    const diffColor =
                                        row.diff === 0
                                            ? "text-muted-foreground"
                                            : positive
                                              ? "text-green-600 dark:text-green-400"
                                              : "text-red-600 dark:text-red-400";
                                    return (
                                        <div
                                            key={`${row.category}|||${row.subcategory}|||${row.movementType}`}
                                            className="flex items-center border-b border-border/50 hover:bg-muted/30 text-sm absolute w-full"
                                            style={{
                                                height: `${virtualRow.size}px`,
                                                transform: `translateY(${virtualRow.start}px)`,
                                            }}
                                        >
                                            <div
                                                className="w-[140px] px-3 shrink-0 text-muted-foreground truncate text-xs"
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
                                                className={`w-[130px] px-3 shrink-0 text-right tabular-nums ${
                                                    row.movementType === "D"
                                                        ? "text-red-600 dark:text-red-400"
                                                        : "text-green-600 dark:text-green-400"
                                                }`}
                                            >
                                                {formatCurrency(row.valueP1, locale)}
                                            </div>
                                            <div
                                                className={`w-[130px] px-3 shrink-0 text-right tabular-nums ${
                                                    row.movementType === "D"
                                                        ? "text-red-600 dark:text-red-400"
                                                        : "text-green-600 dark:text-green-400"
                                                }`}
                                            >
                                                {formatCurrency(row.valueP2, locale)}
                                            </div>
                                            <div
                                                className={`w-[120px] px-3 shrink-0 text-right tabular-nums ${diffColor}`}
                                            >
                                                {row.diff >= 0 ? "+" : ""}
                                                {formatCurrency(row.diff, locale)}
                                            </div>
                                            <div
                                                className={`w-[80px] px-3 shrink-0 text-right tabular-nums text-xs ${diffColor}`}
                                            >
                                                {formatPct(row.pctChange, locale)}
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
