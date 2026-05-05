"use client";

import { useEffect, useRef, useState } from "react";
import { useVirtualizer } from "@tanstack/react-virtual";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { RefreshCw, AlertTriangle } from "lucide-react";

interface ScrapeRun {
    id: string;
    executedAt: number;
    status: string;
    errors: string | null;
    durationSeconds: number | null;
}

interface ApiResponse {
    runs: ScrapeRun[];
    missingPeriods: string[];
}

function formatDateTime(ts: number): string {
    const d = new Date(ts);
    const dd = String(d.getDate()).padStart(2, "0");
    const mm = String(d.getMonth() + 1).padStart(2, "0");
    const yyyy = d.getFullYear();
    const hh = String(d.getHours()).padStart(2, "0");
    const min = String(d.getMinutes()).padStart(2, "0");
    return `${dd}/${mm}/${yyyy} ${hh}:${min}`;
}

function StatusBadge({ status }: { status: string }) {
    if (status === "success") {
        return (
            <Badge className="bg-green-100 text-green-800 border-green-300 hover:bg-green-100" variant="outline">
                success
            </Badge>
        );
    }
    if (status === "error") {
        return (
            <Badge className="bg-red-100 text-red-800 border-red-300 hover:bg-red-100" variant="outline">
                error
            </Badge>
        );
    }
    if (status === "running") {
        return (
            <Badge className="bg-yellow-100 text-yellow-800 border-yellow-300 hover:bg-yellow-100" variant="outline">
                running
            </Badge>
        );
    }
    return <Badge variant="outline">{status}</Badge>;
}

export default function ScrapeRunsClient() {
    const [runs, setRuns] = useState<ScrapeRun[]>([]);
    const [missingPeriods, setMissingPeriods] = useState<string[]>([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);

    useEffect(() => {
        fetch("/api/scrape-runs")
            .then(res => {
                if (!res.ok) throw new Error("Failed to fetch scrape runs");
                return res.json();
            })
            .then((data: ApiResponse) => {
                setRuns(data.runs);
                setMissingPeriods(data.missingPeriods);
            })
            .catch(e => setError(e.message))
            .finally(() => setLoading(false));
    }, []);

    const parentRef = useRef<HTMLDivElement>(null);
    const virtualizer = useVirtualizer({
        count: runs.length,
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
        <div className="flex-1 flex flex-col min-h-0 gap-4">
            {missingPeriods.length > 0 && (
                <Card className="border-yellow-300 bg-yellow-50">
                    <CardHeader className="pb-2">
                        <CardTitle className="flex items-center gap-2 text-base text-yellow-800">
                            <AlertTriangle className="h-4 w-4" />
                            Períodos Faltando
                        </CardTitle>
                    </CardHeader>
                    <CardContent>
                        <p className="text-sm text-yellow-700 mb-2">
                            Os seguintes períodos não possuem prestações de contas:
                        </p>
                        <div className="flex flex-wrap gap-2">
                            {missingPeriods.map(period => (
                                <Badge
                                    key={period}
                                    variant="outline"
                                    className="border-yellow-400 text-yellow-800 bg-yellow-100"
                                >
                                    {period}
                                </Badge>
                            ))}
                        </div>
                    </CardContent>
                </Card>
            )}

            <Card className="flex-1 flex flex-col min-h-0">
                <CardHeader className="pb-3">
                    <CardTitle className="flex items-center gap-2 text-xl">
                        <RefreshCw className="h-5 w-5" />
                        Scrape Runs
                    </CardTitle>
                </CardHeader>
                <CardContent className="flex-1 flex flex-col min-h-0">
                    <div className="text-sm text-muted-foreground mb-3">
                        {loading ? "Carregando..." : `${runs.length} coletas`}
                    </div>

                    <div className="rounded-md border flex-1 flex flex-col min-h-0">
                        {/* Header */}
                        <div className="flex bg-muted/50 text-xs font-medium text-muted-foreground border-b shrink-0">
                            <div className="w-[160px] px-3 py-2 shrink-0">Data</div>
                            <div className="w-[100px] px-3 py-2 shrink-0">Status</div>
                            <div className="w-[100px] px-3 py-2 shrink-0 text-right">Duração (s)</div>
                            <div className="flex-1 px-3 py-2 min-w-0">Erros</div>
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
                                    const run = runs[virtualRow.index];
                                    return (
                                        <div
                                            key={run.id}
                                            className="flex items-center border-b border-border/50 hover:bg-muted/30 text-sm absolute w-full"
                                            style={{
                                                height: `${virtualRow.size}px`,
                                                transform: `translateY(${virtualRow.start}px)`,
                                            }}
                                        >
                                            <div className="w-[160px] px-3 shrink-0 whitespace-nowrap tabular-nums">
                                                {formatDateTime(run.executedAt)}
                                            </div>
                                            <div className="w-[100px] px-3 shrink-0">
                                                <StatusBadge status={run.status} />
                                            </div>
                                            <div className="w-[100px] px-3 shrink-0 text-right tabular-nums text-muted-foreground">
                                                {run.durationSeconds != null ? run.durationSeconds.toFixed(1) : "-"}
                                            </div>
                                            <div
                                                className="flex-1 px-3 min-w-0 truncate text-xs text-muted-foreground"
                                                title={run.errors ?? undefined}
                                            >
                                                {run.errors ?? "-"}
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
