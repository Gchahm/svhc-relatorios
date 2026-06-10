"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import Link from "next/link";
import { useVirtualizer } from "@tanstack/react-virtual";
import { Badge } from "@/components/ui/badge";
import { MultiSelect } from "@/components/ui/multi-select";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { AlertTriangle, ExternalLink } from "lucide-react";

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

/**
 * Entry ids an alert concerns, parsed from its (untyped JSON) metadata. Covers both the
 * per-attachment mismatch alerts (single `entry_id`) and the entry-level alerts that store
 * an `entry_ids` array (duplicate_billing, duplicate_entry, negative_credit,
 * large_expense_no_attachment). Period/category-level alerts have neither → no links.
 * Parses defensively: any malformed/absent metadata yields no links rather than throwing.
 */
function affectedEntryIds(metadata: string | null): string[] {
    if (!metadata) return [];
    try {
        const meta = JSON.parse(metadata) as { entry_ids?: unknown; entry_id?: unknown };
        if (Array.isArray(meta.entry_ids)) {
            return meta.entry_ids.filter((v): v is string => typeof v === "string");
        }
        if (typeof meta.entry_id === "string") return [meta.entry_id];
        return [];
    } catch {
        return [];
    }
}

/** Deep link to the entries page focused on one entry, with the detail dialog auto-opened. */
function entryHref(period: string, entryId: string): string {
    return `/dashboard/entries?period=${encodeURIComponent(period)}&entry=${encodeURIComponent(entryId)}`;
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

function SeverityBadge({ severity }: { severity: string }) {
    if (severity === "critical") {
        return <Badge variant="destructive">{severity}</Badge>;
    }
    if (severity === "warning") {
        return (
            <Badge variant="outline" className="border-yellow-400 text-yellow-700">
                {severity}
            </Badge>
        );
    }
    return <Badge variant="secondary">{severity}</Badge>;
}

function StatusBadge({ resolved }: { resolved: boolean }) {
    if (resolved) {
        return (
            <Badge variant="outline" className="border-green-400 text-green-700">
                resolved
            </Badge>
        );
    }
    return <Badge variant="destructive">active</Badge>;
}

export default function AlertsClient() {
    const [data, setData] = useState<AlertRow[]>([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);

    const [selectedSeverities, setSelectedSeverities] = useState<string[]>([]);
    const [selectedPeriods, setSelectedPeriods] = useState<string[]>([]);
    const [selectedTypes, setSelectedTypes] = useState<string[]>([]);
    const [selectedStatuses, setSelectedStatuses] = useState<string[]>([]);

    const fetchData = () => {
        setLoading(true);
        fetch("/api/alerts")
            .then(res => {
                if (!res.ok) throw new Error("Failed to fetch alerts");
                return res.json();
            })
            .then(setData)
            .catch(e => setError(e.message))
            .finally(() => setLoading(false));
    };

    useEffect(() => {
        fetchData();
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

    const handleRowClick = async (row: AlertRow) => {
        const newResolved = !row.resolved;
        let notes: string | null = row.notes;

        if (newResolved) {
            const input = window.prompt(`Resolving alert: "${row.title}"\n\nAdd optional notes:`, row.notes ?? "");
            if (input === null) return; // cancelled
            notes = input.trim() || null;
        }

        try {
            const res = await fetch(`/api/alerts/${row.id}`, {
                method: "PATCH",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ resolved: newResolved, notes }),
            });
            if (!res.ok) throw new Error("Failed to update alert");
            const updated: AlertRow = await res.json();
            setData(prev => prev.map(r => (r.id === updated.id ? updated : r)));
        } catch (e) {
            alert((e as Error).message);
        }
    };

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
                                                onClick={() => handleRowClick(row)}
                                                title="Click to toggle resolved status"
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
