"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { useVirtualizer } from "@tanstack/react-virtual";
import { MultiSelect } from "@/components/ui/multi-select";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Store } from "lucide-react";
import { useTranslation, useLocale } from "@/lib/i18n/client";
import { formatCurrency, formatPercent } from "@/lib/i18n/formatters.client";
import { plural } from "@/lib/i18n/plural";

interface VendorRow {
    vendorId: string;
    name: string;
    period: string;
    total: number;
    entryCount: number;
}

interface AggregatedVendor {
    vendorId: string;
    name: string;
    total: number;
    entryCount: number;
    periodCount: number;
}

export default function VendorsClient() {
    const t = useTranslation();
    const locale = useLocale();
    const [data, setData] = useState<VendorRow[]>([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);

    const [selectedPeriods, setSelectedPeriods] = useState<string[]>([]);

    useEffect(() => {
        fetch("/api/vendors")
            .then(res => {
                if (!res.ok) throw new Error("Failed to fetch vendors");
                return res.json();
            })
            .then(setData)
            .catch(e => setError(e.message))
            .finally(() => setLoading(false));
    }, []);

    const periodOptions = useMemo(
        () =>
            [...new Set(data.map(r => r.period))]
                .sort()
                .reverse()
                .map(v => ({ value: v, label: v })),
        [data]
    );

    const aggregated = useMemo<AggregatedVendor[]>(() => {
        const filtered = selectedPeriods.length === 0 ? data : data.filter(r => selectedPeriods.includes(r.period));

        const map = new Map<string, AggregatedVendor>();
        for (const row of filtered) {
            const existing = map.get(row.vendorId);
            if (existing) {
                existing.total += row.total;
                existing.entryCount += row.entryCount;
                existing.periodCount += 1;
            } else {
                map.set(row.vendorId, {
                    vendorId: row.vendorId,
                    name: row.name,
                    total: row.total,
                    entryCount: row.entryCount,
                    periodCount: 1,
                });
            }
        }

        return [...map.values()].sort((a, b) => b.total - a.total);
    }, [data, selectedPeriods]);

    const grandTotal = useMemo(() => aggregated.reduce((sum, r) => sum + r.total, 0), [aggregated]);

    const parentRef = useRef<HTMLDivElement>(null);
    const virtualizer = useVirtualizer({
        count: aggregated.length,
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
                        <Store className="h-5 w-5" />
                        {t("page.vendors_title")}
                    </CardTitle>
                </CardHeader>
                <CardContent className="space-y-4 flex-1 flex flex-col min-h-0">
                    {/* Filters */}
                    <div className="flex flex-wrap gap-3 items-end">
                        <div className="w-[200px]">
                            <label className="block text-xs text-muted-foreground mb-1">{t("filter.periods")}</label>
                            <MultiSelect
                                options={periodOptions}
                                selected={selectedPeriods}
                                onSelectedChange={setSelectedPeriods}
                                placeholder={t("form.all")}
                                className="w-full"
                            />
                        </div>
                    </div>

                    {/* Summary */}
                    <div className="flex items-center gap-4 text-sm">
                        <span className="text-muted-foreground">
                            {loading
                                ? t("form.loading")
                                : `${aggregated.length} ${plural(t, "count.vendors", aggregated.length)}`}
                        </span>
                        {!loading && (
                            <Badge
                                variant="outline"
                                className="text-red-700 dark:text-red-400 border-red-300 dark:border-red-800"
                            >
                                {t("summary.total")}: {formatCurrency(grandTotal, locale)}
                            </Badge>
                        )}
                    </div>

                    {/* Table */}
                    <div className="rounded-md border flex-1 flex flex-col min-h-0">
                        <div className="flex bg-muted/50 text-xs font-medium text-muted-foreground border-b shrink-0">
                            <div className="flex-1 px-3 py-2 min-w-0">{t("table.vendor_name")}</div>
                            <div className="w-[130px] px-3 py-2 shrink-0 text-right">{t("table.total")}</div>
                            <div className="w-[80px] px-3 py-2 shrink-0 text-right">{t("table.pct_of_total")}</div>
                            <div className="w-[70px] px-3 py-2 shrink-0 text-right">{t("table.entries")}</div>
                            <div className="w-[70px] px-3 py-2 shrink-0 text-right">{t("filter.periods")}</div>
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
                                    const row = aggregated[virtualRow.index];
                                    const pct = grandTotal > 0 ? row.total / grandTotal : 0;
                                    return (
                                        <div
                                            key={row.vendorId}
                                            className="flex items-center border-b border-border/50 hover:bg-muted/30 text-sm absolute w-full"
                                            style={{
                                                height: `${virtualRow.size}px`,
                                                transform: `translateY(${virtualRow.start}px)`,
                                            }}
                                        >
                                            <div className="flex-1 px-3 min-w-0 truncate" title={row.name}>
                                                {row.name}
                                            </div>
                                            <div className="w-[130px] px-3 shrink-0 text-right tabular-nums text-red-600 dark:text-red-400">
                                                {formatCurrency(row.total, locale)}
                                            </div>
                                            <div className="w-[80px] px-3 shrink-0 text-right tabular-nums text-muted-foreground">
                                                {formatPercent(pct, 1, locale)}
                                            </div>
                                            <div className="w-[70px] px-3 shrink-0 text-right tabular-nums text-muted-foreground">
                                                {row.entryCount}
                                            </div>
                                            <div className="w-[70px] px-3 shrink-0 text-right tabular-nums text-muted-foreground">
                                                {row.periodCount}
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
