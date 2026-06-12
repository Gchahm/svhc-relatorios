"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useVirtualizer } from "@tanstack/react-virtual";
import { Badge } from "@/components/ui/badge";
import { MultiSelect } from "@/components/ui/multi-select";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { AlertTriangle, ExternalLink } from "lucide-react";
import { affectedEntryIds, entryHref, SeverityBadge, StatusBadge } from "./alerts";

interface AlertRow {
    id: string;
    type: string;
    severity: string;
    title: string;
    description: string;
    referencePeriod: string;
    resolved: boolean;
    resolvedAt: number | null;
    notes: string | null;
    metadata: string | null;
}

/** Renders an alert's affected-entry links: nothing / one inline link / a popover list. */
function EntryLinks({ period, entryIds }: { period: string; entryIds: string[] }) {
    if (entryIds.length === 0) {
        return <span className="text-muted-foreground text-xs">—</span>;
    }
    if (entryIds.length === 1) {
        return (
            <Link
                href={entryHref(period, entryIds[0])}
                onClick={e => e.stopPropagation()}
                className="inline-flex items-center gap-1 text-xs text-blue-600 hover:underline"
            >
                Open <ExternalLink className="h-3 w-3" />
            </Link>
        );
    }
    return (
        <Popover>
            <PopoverTrigger onClick={e => e.stopPropagation()} className="text-xs text-blue-600 hover:underline">
                {entryIds.length} entries ▾
            </PopoverTrigger>
            <PopoverContent className="w-44 p-1" onClick={e => e.stopPropagation()}>
                <div className="flex flex-col">
                    {entryIds.map((id, i) => (
                        <Link
                            key={id}
                            href={entryHref(period, id)}
                            onClick={e => e.stopPropagation()}
                            className="inline-flex items-center justify-between gap-1 rounded px-2 py-1 text-xs text-blue-600 hover:bg-muted hover:underline"
                        >
                            Entry {i + 1} <ExternalLink className="h-3 w-3" />
                        </Link>
                    ))}
                </div>
            </PopoverContent>
        </Popover>
    );
}

export default function AlertsClient() {
    const router = useRouter();
    const [data, setData] = useState<AlertRow[]>([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);

    const [selectedSeverities, setSelectedSeverities] = useState<string[]>([]);
    const [selectedPeriods, setSelectedPeriods] = useState<string[]>([]);
    const [selectedTypes, setSelectedTypes] = useState<string[]>([]);
    const [selectedStatuses, setSelectedStatuses] = useState<string[]>([]);

    // Monotonic request token: with several refetch triggers (mount, tab focus, page becoming
    // visible) two requests can be in flight at once, so a slower earlier response must not
    // overwrite the newer data — only the latest request applies its result (032 FR-005).
    const requestSeq = useRef(0);

    const fetchData = () => {
        const seq = ++requestSeq.current;
        setLoading(true);
        fetch("/api/alerts")
            .then(res => {
                if (!res.ok) throw new Error("Failed to fetch alerts");
                return res.json();
            })
            .then(rows => {
                if (seq === requestSeq.current) setData(rows);
            })
            .catch(e => {
                if (seq === requestSeq.current) setError(e.message);
            })
            .finally(() => {
                if (seq === requestSeq.current) setLoading(false);
            });
    };

    useEffect(() => {
        fetchData();
        // Re-fetch when this list becomes current again so it reflects the latest status without a
        // manual refresh (032 FR-001/FR-002). `focus` covers returning from another browser tab;
        // `visibilitychange` covers same-tab in-app navigation back from the detail page after a
        // resolve/reopen, which does not fire `focus`.
        const onFocus = () => fetchData();
        const onVisibility = () => {
            if (document.visibilityState === "visible") fetchData();
        };
        window.addEventListener("focus", onFocus);
        document.addEventListener("visibilitychange", onVisibility);
        return () => {
            window.removeEventListener("focus", onFocus);
            document.removeEventListener("visibilitychange", onVisibility);
        };
    }, []);

    const severityOptions = [
        { value: "critical", label: "Critical" },
        { value: "warning", label: "Warning" },
        { value: "info", label: "Info" },
    ];

    const periodOptions = useMemo(
        () =>
            [...new Set(data.map(r => r.referencePeriod))]
                .sort()
                .reverse()
                .map(v => ({ value: v, label: v })),
        [data]
    );

    const typeOptions = useMemo(
        () => [...new Set(data.map(r => r.type))].sort().map(v => ({ value: v, label: v })),
        [data]
    );

    const statusOptions = [
        { value: "active", label: "Active" },
        { value: "resolved", label: "Resolved" },
    ];

    const filtered = useMemo(() => {
        return data.filter(r => {
            if (selectedSeverities.length > 0 && !selectedSeverities.includes(r.severity)) return false;
            if (selectedPeriods.length > 0 && !selectedPeriods.includes(r.referencePeriod)) return false;
            if (selectedTypes.length > 0 && !selectedTypes.includes(r.type)) return false;
            if (selectedStatuses.length > 0) {
                const status = r.resolved ? "resolved" : "active";
                if (!selectedStatuses.includes(status)) return false;
            }
            return true;
        });
    }, [data, selectedSeverities, selectedPeriods, selectedTypes, selectedStatuses]);

    const activeCounts = useMemo(() => {
        const active = data.filter(r => !r.resolved);
        return {
            critical: active.filter(r => r.severity === "critical").length,
            warning: active.filter(r => r.severity === "warning").length,
            info: active.filter(r => r.severity === "info").length,
        };
    }, [data]);

    const parentRef = useRef<HTMLDivElement>(null);
    const virtualizer = useVirtualizer({
        count: filtered.length,
        getScrollElement: () => parentRef.current,
        estimateSize: () => 40,
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
        <div className="flex-1 flex flex-col min-h-0">
            <Card className="flex-1 flex flex-col min-h-0">
                <CardHeader className="pb-3">
                    <CardTitle className="flex items-center gap-2 text-xl">
                        <AlertTriangle className="h-5 w-5" />
                        Alerts
                    </CardTitle>
                </CardHeader>
                <CardContent className="space-y-4 flex-1 flex flex-col min-h-0">
                    {/* Summary badges */}
                    <div className="flex items-center gap-3 text-sm flex-wrap">
                        <span className="text-muted-foreground">
                            {loading ? "Loading..." : `${filtered.length} alerts`}
                        </span>
                        {!loading && (
                            <>
                                {activeCounts.critical > 0 && (
                                    <Badge variant="destructive">{activeCounts.critical} critical</Badge>
                                )}
                                {activeCounts.warning > 0 && (
                                    <Badge variant="outline" className="border-yellow-400 text-yellow-700">
                                        {activeCounts.warning} warning
                                    </Badge>
                                )}
                                {activeCounts.info > 0 && <Badge variant="secondary">{activeCounts.info} info</Badge>}
                            </>
                        )}
                    </div>

                    {/* Filters */}
                    <div className="flex flex-wrap gap-3 items-end">
                        <div className="w-[160px]">
                            <label className="block text-xs text-muted-foreground mb-1">Severity</label>
                            <MultiSelect
                                options={severityOptions}
                                selected={selectedSeverities}
                                onSelectedChange={setSelectedSeverities}
                                placeholder="All"
                                className="w-full"
                            />
                        </div>
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
                            <label className="block text-xs text-muted-foreground mb-1">Type</label>
                            <MultiSelect
                                options={typeOptions}
                                selected={selectedTypes}
                                onSelectedChange={setSelectedTypes}
                                placeholder="All"
                                className="w-full"
                            />
                        </div>
                        <div className="w-[160px]">
                            <label className="block text-xs text-muted-foreground mb-1">Status</label>
                            <MultiSelect
                                options={statusOptions}
                                selected={selectedStatuses}
                                onSelectedChange={setSelectedStatuses}
                                placeholder="All"
                                className="w-full"
                            />
                        </div>
                    </div>

                    {/* Table */}
                    <div className="rounded-md border flex-1 flex flex-col min-h-0">
                        <div className="flex bg-muted/50 text-xs font-medium text-muted-foreground border-b shrink-0">
                            <div className="w-[80px] px-3 py-2 shrink-0">Period</div>
                            <div className="w-[90px] px-3 py-2 shrink-0">Severity</div>
                            <div className="w-[200px] px-3 py-2 shrink-0">Title</div>
                            <div className="flex-1 px-3 py-2 min-w-0">Description</div>
                            <div className="w-[100px] px-3 py-2 shrink-0">Entries</div>
                            <div className="w-[90px] px-3 py-2 shrink-0 text-right">Status</div>
                        </div>

                        <div ref={parentRef} className="flex-1 overflow-auto min-h-0">
                            {filtered.length === 0 && !loading ? (
                                <div className="py-12 text-center text-sm text-muted-foreground">No alerts found.</div>
                            ) : (
                                <div
                                    style={{
                                        height: `${virtualizer.getTotalSize()}px`,
                                        width: "100%",
                                        position: "relative",
                                    }}
                                >
                                    {virtualizer.getVirtualItems().map(virtualRow => {
                                        const row = filtered[virtualRow.index];
                                        const entryIds = affectedEntryIds(row.metadata);
                                        return (
                                            <div
                                                key={row.id}
                                                className="flex items-center border-b border-border/50 hover:bg-muted/30 text-sm absolute w-full cursor-pointer"
                                                style={{
                                                    height: `${virtualRow.size}px`,
                                                    transform: `translateY(${virtualRow.start}px)`,
                                                }}
                                                onClick={() => router.push(`/dashboard/alerts/${row.id}`)}
                                                title="Click to open the alert detail page"
                                            >
                                                <div className="w-[80px] px-3 shrink-0 text-muted-foreground text-xs">
                                                    {row.referencePeriod}
                                                </div>
                                                <div className="w-[90px] px-3 shrink-0">
                                                    <SeverityBadge severity={row.severity} />
                                                </div>
                                                <div
                                                    className="w-[200px] px-3 shrink-0 truncate font-medium"
                                                    title={row.title}
                                                >
                                                    {row.title}
                                                </div>
                                                <div
                                                    className="flex-1 px-3 min-w-0 truncate text-muted-foreground text-xs"
                                                    title={row.description}
                                                >
                                                    {row.description}
                                                </div>
                                                <div className="w-[100px] px-3 shrink-0">
                                                    <EntryLinks period={row.referencePeriod} entryIds={entryIds} />
                                                </div>
                                                <div className="w-[90px] px-3 shrink-0 flex justify-end">
                                                    <StatusBadge resolved={row.resolved} />
                                                </div>
                                            </div>
                                        );
                                    })}
                                </div>
                            )}
                        </div>
                    </div>
                </CardContent>
            </Card>
        </div>
    );
}
