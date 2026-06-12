"use client";

import { useEffect, useRef, useState } from "react";
import { useVirtualizer } from "@tanstack/react-virtual";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { FileSpreadsheet } from "lucide-react";
import { useTranslation, useLocale } from "@/lib/i18n/client";
import { formatCurrency } from "@/lib/i18n/formatters.client";
import { plural } from "@/lib/i18n/plural";

interface AccountabilityReport {
    id: string;
    period: string;
    totalRevenue: number;
    totalExpenses: number;
    openingBalance: number;
    monthBalance: number;
    accumulatedBalance: number;
    sourceUrl: string;
}

function colorBySign(value: number): string {
    if (value > 0) return "text-green-600";
    if (value < 0) return "text-red-600";
    return "";
}

export default function ReportsClient() {
    const t = useTranslation();
    const locale = useLocale();
    const [reports, setReports] = useState<AccountabilityReport[]>([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);

    useEffect(() => {
        fetch("/api/reports")
            .then(res => {
                if (!res.ok) throw new Error("Failed to fetch reports");
                return res.json();
            })
            .then(setReports)
            .catch(e => setError(e.message))
            .finally(() => setLoading(false));
    }, []);

    const parentRef = useRef<HTMLDivElement>(null);
    const virtualizer = useVirtualizer({
        count: reports.length,
        getScrollElement: () => parentRef.current,
        estimateSize: () => 36,
        overscan: 20,
    });

    if (error) {
        return (
            <Card>
                <CardContent className="py-12 text-center text-red-500">
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
                        <FileSpreadsheet className="h-5 w-5" />
                        {t("page.reports_title")}
                    </CardTitle>
                </CardHeader>
                <CardContent className="space-y-4 flex-1 flex flex-col min-h-0">
                    {/* Summary */}
                    <div className="text-sm text-muted-foreground">
                        {loading
                            ? t("form.loading")
                            : `${reports.length} ${plural(t, "count.periods", reports.length)}`}
                    </div>

                    {/* Table */}
                    <div className="rounded-md border flex-1 flex flex-col min-h-0">
                        {/* Header */}
                        <div className="flex bg-muted/50 text-xs font-medium text-muted-foreground border-b shrink-0">
                            <div className="w-[90px] px-3 py-2 shrink-0">{t("table.period")}</div>
                            <div className="w-[140px] px-3 py-2 shrink-0 text-right">{t("table.revenue")}</div>
                            <div className="w-[140px] px-3 py-2 shrink-0 text-right">{t("table.expenses")}</div>
                            <div className="w-[140px] px-3 py-2 shrink-0 text-right">{t("table.month_balance")}</div>
                            <div className="flex-1 px-3 py-2 min-w-0 text-right">{t("table.accumulated_balance")}</div>
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
                                    const report = reports[virtualRow.index];
                                    return (
                                        <div
                                            key={report.id}
                                            className="flex items-center border-b border-border/50 hover:bg-muted/30 text-sm absolute w-full"
                                            style={{
                                                height: `${virtualRow.size}px`,
                                                transform: `translateY(${virtualRow.start}px)`,
                                            }}
                                        >
                                            <div className="w-[90px] px-3 shrink-0 font-mono">{report.period}</div>
                                            <div className="w-[140px] px-3 shrink-0 text-right tabular-nums text-green-600">
                                                {formatCurrency(report.totalRevenue, locale)}
                                            </div>
                                            <div className="w-[140px] px-3 shrink-0 text-right tabular-nums text-red-600">
                                                {formatCurrency(report.totalExpenses, locale)}
                                            </div>
                                            <div
                                                className={`w-[140px] px-3 shrink-0 text-right tabular-nums ${colorBySign(report.monthBalance)}`}
                                            >
                                                {formatCurrency(report.monthBalance, locale)}
                                            </div>
                                            <div
                                                className={`flex-1 px-3 min-w-0 text-right tabular-nums ${colorBySign(report.accumulatedBalance)}`}
                                            >
                                                {formatCurrency(report.accumulatedBalance, locale)}
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
