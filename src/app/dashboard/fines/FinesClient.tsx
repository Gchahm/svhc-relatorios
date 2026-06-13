"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { useVirtualizer } from "@tanstack/react-virtual";
import { Badge } from "@/components/ui/badge";
import { MultiSelect } from "@/components/ui/multi-select";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Gavel } from "lucide-react";
import { useTranslation, useLocale } from "@/lib/i18n/client";
import { formatCurrency, formatDate } from "@/lib/i18n/formatters.client";
import { plural } from "@/lib/i18n/plural";

interface Fine {
    id: string;
    period: string;
    date: string;
    unitCode: string | null;
    description: string;
    amount: number;
}

interface FineRow extends Fine {
    reason: string;
    block: string;
}

const REASON_RE = /^MULTA - (.+?)(?:\s*-\s*\d{2}\/\d{2}\/\d{4}.*)?$/;

function extractReason(description: string): string {
    const match = REASON_RE.exec(description);
    return match ? match[1].trim() : description;
}

function extractBlock(unitCode: string | null): string {
    if (!unitCode) return "-";
    // Unit codes like "205C" — last character is the block letter
    const last = unitCode.slice(-1);
    return /[A-Za-z]/.test(last) ? last.toUpperCase() : "-";
}

export default function FinesClient() {
    const t = useTranslation();
    const locale = useLocale();
    const [fines, setFines] = useState<Fine[]>([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);

    // Filters
    const [selectedPeriods, setSelectedPeriods] = useState<string[]>([]);
    const [selectedBlocks, setSelectedBlocks] = useState<string[]>([]);
    const [selectedReasons, setSelectedReasons] = useState<string[]>([]);

    useEffect(() => {
        fetch("/api/fines")
            .then(res => {
                if (!res.ok) throw new Error("Failed to fetch fines");
                return res.json();
            })
            .then((data: Fine[]) => setFines(data))
            .catch(e => setError(e.message))
            .finally(() => setLoading(false));
    }, []);

    // Enrich rows with derived fields
    const rows: FineRow[] = useMemo(
        () =>
            fines.map(f => ({
                ...f,
                reason: extractReason(f.description),
                block: extractBlock(f.unitCode),
            })),
        [fines]
    );

    // Derive filter options
    const periodOptions = useMemo(
        () => [...new Set(rows.map(r => r.period))].sort().map(v => ({ value: v, label: v })),
        [rows]
    );
    const blockOptions = useMemo(
        () =>
            [...new Set(rows.map(r => r.block))]
                .filter(b => b !== "-")
                .sort()
                .map(v => ({ value: v, label: `${t("filter.block")} ${v}` })),
        [rows, t]
    );
    const reasonOptions = useMemo(
        () => [...new Set(rows.map(r => r.reason))].sort().map(v => ({ value: v, label: v })),
        [rows]
    );

    // Apply filters
    const filtered = useMemo(
        () =>
            rows.filter(r => {
                if (selectedPeriods.length > 0 && !selectedPeriods.includes(r.period)) return false;
                if (selectedBlocks.length > 0 && !selectedBlocks.includes(r.block)) return false;
                if (selectedReasons.length > 0 && !selectedReasons.includes(r.reason)) return false;
                return true;
            }),
        [rows, selectedPeriods, selectedBlocks, selectedReasons]
    );

    // Summary totals
    const totalAmount = useMemo(() => filtered.reduce((sum, r) => sum + r.amount, 0), [filtered]);

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
        <div className="flex-1 flex flex-col min-h-0">
            <Card className="flex-1 flex flex-col min-h-0">
                <CardHeader className="pb-3">
                    <CardTitle className="flex items-center gap-2 text-xl">
                        <Gavel className="h-5 w-5" />
                        {t("page.fines_title")}
                    </CardTitle>
                </CardHeader>
                <CardContent className="space-y-4 flex-1 flex flex-col min-h-0">
                    {/* Filters */}
                    <div className="flex flex-wrap gap-3 items-end">
                        <div className="w-[200px]">
                            <label className="block text-xs text-muted-foreground mb-1">{t("filter.period")}</label>
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
                        <div className="flex-1 min-w-[200px]">
                            <label className="block text-xs text-muted-foreground mb-1">{t("filter.reason")}</label>
                            <MultiSelect
                                options={reasonOptions}
                                selected={selectedReasons}
                                onSelectedChange={setSelectedReasons}
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
                                : `${filtered.length} ${plural(t, "count.fines", filtered.length)}`}
                        </span>
                        {!loading && (
                            <Badge
                                variant="outline"
                                className="text-red-700 dark:text-red-400 border-red-300 dark:border-red-800"
                            >
                                {t("summary.total")}: {formatCurrency(totalAmount, locale)}
                            </Badge>
                        )}
                    </div>

                    {/* Table */}
                    <div className="rounded-md border flex-1 flex flex-col min-h-0">
                        {/* Header */}
                        <div className="flex bg-muted/50 text-xs font-medium text-muted-foreground border-b shrink-0">
                            <div className="w-[90px] px-3 py-2 shrink-0">{t("table.period")}</div>
                            <div className="w-[90px] px-3 py-2 shrink-0">{t("table.date")}</div>
                            <div className="w-[60px] px-3 py-2 shrink-0">{t("table.unit")}</div>
                            <div className="flex-1 px-3 py-2 min-w-0">{t("table.reason")}</div>
                            <div className="w-[120px] px-3 py-2 shrink-0 text-right">{t("table.amount")}</div>
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
                                    const row = filtered[virtualRow.index];
                                    return (
                                        <div
                                            key={row.id}
                                            className="flex items-center border-b border-border/50 hover:bg-muted/30 text-sm absolute w-full"
                                            style={{
                                                height: `${virtualRow.size}px`,
                                                transform: `translateY(${virtualRow.start}px)`,
                                            }}
                                        >
                                            <div className="w-[90px] px-3 shrink-0 text-muted-foreground text-xs whitespace-nowrap">
                                                {row.period}
                                            </div>
                                            <div className="w-[90px] px-3 shrink-0 whitespace-nowrap">
                                                {formatDate(row.date, locale)}
                                            </div>
                                            <div className="w-[60px] px-3 shrink-0 text-muted-foreground text-xs">
                                                {row.unitCode ?? "-"}
                                            </div>
                                            <div className="flex-1 px-3 min-w-0 truncate" title={row.reason}>
                                                {row.reason}
                                            </div>
                                            <div className="w-[120px] px-3 shrink-0 text-right tabular-nums text-red-600 dark:text-red-400">
                                                {formatCurrency(row.amount, locale)}
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
