"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { useVirtualizer } from "@tanstack/react-virtual";
import { MultiSelect } from "@/components/ui/multi-select";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Building2 } from "lucide-react";
import { useTranslation, useLocale } from "@/lib/i18n/client";
import { formatCurrency } from "@/lib/i18n/formatters.client";
import { plural } from "@/lib/i18n/plural";

interface UnitPeriodRow {
    unitId: string;
    code: string;
    block: string;
    number: number;
    period: string;
    total: number;
    entryCount: number;
}

interface AggregatedUnit {
    unitId: string;
    code: string;
    block: string;
    total: number;
    entryCount: number;
    periodCount: number;
}

export default function UnitsClient() {
    const t = useTranslation();
    const locale = useLocale();
    const [data, setData] = useState<UnitPeriodRow[]>([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);

    const [selectedPeriods, setSelectedPeriods] = useState<string[]>([]);
    const [selectedBlocks, setSelectedBlocks] = useState<string[]>([]);

    useEffect(() => {
        fetch("/api/units")
            .then(res => {
                if (!res.ok) throw new Error("Failed to fetch units");
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

    const blockOptions = useMemo(
        () => [...new Set(data.map(r => r.block))].sort().map(v => ({ value: v, label: `${t("filter.block")} ${v}` })),
        [data, t]
    );

    const aggregated = useMemo<AggregatedUnit[]>(() => {
        const filtered = data.filter(r => {
            if (selectedPeriods.length > 0 && !selectedPeriods.includes(r.period)) return false;
            if (selectedBlocks.length > 0 && !selectedBlocks.includes(r.block)) return false;
            return true;
        });

        const map = new Map<string, AggregatedUnit>();
        for (const r of filtered) {
            const existing = map.get(r.unitId);
            if (existing) {
                existing.total += r.total;
                existing.entryCount += r.entryCount;
                existing.periodCount += 1;
            } else {
                map.set(r.unitId, {
                    unitId: r.unitId,
                    code: r.code,
                    block: r.block,
                    total: r.total,
                    entryCount: r.entryCount,
                    periodCount: 1,
                });
            }
        }

        return [...map.values()].sort((a, b) => a.code.localeCompare(b.code));
    }, [data, selectedPeriods, selectedBlocks]);

    const totalAmount = useMemo(() => aggregated.reduce((sum, r) => sum + r.total, 0), [aggregated]);

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
                        <Building2 className="h-5 w-5" />
                        {t("page.units_title")}
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
                        <div className="w-[160px]">
                            <label className="block text-xs text-muted-foreground mb-1">{t("filter.block")}</label>
                            <MultiSelect
                                options={blockOptions}
                                selected={selectedBlocks}
                                onSelectedChange={setSelectedBlocks}
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
                                : `${aggregated.length} ${plural(t, "count.units", aggregated.length)}`}
                        </span>
                        {!loading && (
                            <span className="text-muted-foreground">
                                {t("summary.total")}:{" "}
                                <span className="font-medium text-foreground">
                                    {formatCurrency(totalAmount, locale)}
                                </span>
                            </span>
                        )}
                    </div>

                    {/* Table */}
                    <div className="rounded-md border flex-1 flex flex-col min-h-0">
                        <div className="flex bg-muted/50 text-xs font-medium text-muted-foreground border-b shrink-0">
                            <div className="w-[80px] px-3 py-2 shrink-0">{t("table.code")}</div>
                            <div className="w-[70px] px-3 py-2 shrink-0">{t("table.block")}</div>
                            <div className="flex-1 px-3 py-2 min-w-0" />
                            <div className="w-[140px] px-3 py-2 shrink-0 text-right">{t("table.total_paid")}</div>
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
                                    return (
                                        <div
                                            key={row.unitId}
                                            className="flex items-center border-b border-border/50 hover:bg-muted/30 text-sm absolute w-full"
                                            style={{
                                                height: `${virtualRow.size}px`,
                                                transform: `translateY(${virtualRow.start}px)`,
                                            }}
                                        >
                                            <div className="w-[80px] px-3 shrink-0 font-medium">{row.code}</div>
                                            <div className="w-[70px] px-3 shrink-0 text-muted-foreground text-xs">
                                                {row.block}
                                            </div>
                                            <div className="flex-1 px-3 min-w-0" />
                                            <div className="w-[140px] px-3 shrink-0 text-right tabular-nums">
                                                {formatCurrency(row.total, locale)}
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
