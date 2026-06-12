"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useSearchParams } from "next/navigation";
import { useVirtualizer } from "@tanstack/react-virtual";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { MultiSelect } from "@/components/ui/multi-select";
import { CategoryTree } from "@/components/filters/CategoryTree";
import { SortableHeader, useSort } from "@/components/filters/SortableHeader";
import { Receipt } from "lucide-react";
import AttachmentAnalysisDetailDialog from "./AttachmentAnalysisDetailDialog";
import type { Entry, AttachmentAnalysisRow } from "./types";

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

/** Compact per-row match indicator: green check (OK), red cross (mismatch), em-dash (n/a). */
function MatchCell({ match }: { match: boolean | null | undefined }) {
    if (match === null || match === undefined) {
        return <span className="text-muted-foreground text-xs">—</span>;
    }
    if (match) {
        return (
            <Badge variant="outline" className="border-green-400 text-green-700 text-[10px] px-1 py-0">
                ✓
            </Badge>
        );
    }
    return (
        <Badge variant="destructive" className="text-[10px] px-1 py-0">
            ✗
        </Badge>
    );
}

export default function EntriesClient() {
    // Deep link (from an alert): ?period=<YYYY-MM>&entry=<entryId>. Read once on mount; the
    // period seeds the initial selection and the entry auto-opens its detail dialog after load.
    const searchParams = useSearchParams();
    const deepLinkPeriod = searchParams.get("period");
    const deepLinkEntry = searchParams.get("entry");

    const [entries, setEntries] = useState<Entry[]>([]);
    const [attachmentAnalyses, setAttachmentAnalyses] = useState<AttachmentAnalysisRow[]>([]);
    const [periods, setPeriods] = useState<string[]>([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);

    // Filters — a deep-link period overrides the current-month default.
    const [selectedPeriod, setSelectedPeriod] = useState(deepLinkPeriod || getCurrentPeriod());
    const [selectedSubcategories, setSelectedSubcategories] = useState<string[]>([]);
    const [search, setSearch] = useState("");
    const [selectedDocTypes, setSelectedDocTypes] = useState<string[]>([]);
    const [selectedDocMatchStatus, setSelectedDocMatchStatus] = useState<string[]>([]);

    // Attachment detail dialog
    const [selectedAnalysis, setSelectedAnalysis] = useState<AttachmentAnalysisRow | null>(null);

    // Deep-link target row highlight; the effect below runs once per (period|entry) param set.
    const [highlightedEntryId, setHighlightedEntryId] = useState<string | null>(null);
    const deepLinkHandledRef = useRef<string | null>(null);

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

    // Fetch entries + their period-scoped attachment analyses when period changes
    const fetchEntries = useCallback((period: string) => {
        setLoading(true);
        setError(null);
        const q = encodeURIComponent(period);
        Promise.all([
            fetch(`/api/entries?period=${q}`).then(res => {
                if (!res.ok) throw new Error("Failed to fetch entries");
                return res.json() as Promise<Entry[]>;
            }),
            // Attachment analyses follow the period's entries; a failure here must not blank the ledger.
            fetch(`/api/attachment-analyses?period=${q}`)
                .then(res => (res.ok ? (res.json() as Promise<AttachmentAnalysisRow[]>) : []))
                .catch(() => [] as AttachmentAnalysisRow[]),
        ])
            .then(([entryRows, analysisRows]) => {
                setEntries(entryRows);
                setAttachmentAnalyses(Array.isArray(analysisRows) ? analysisRows : []);
            })
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
        setSearch("");
        setSelectedDocTypes([]);
        setSelectedDocMatchStatus([]);
    };

    // Latest analysis per entry (endpoint orders analyzedAt DESC, so first-seen wins).
    const analysisByEntry = useMemo(() => {
        const map = new Map<string, AttachmentAnalysisRow>();
        for (const a of attachmentAnalyses) {
            if (!map.has(a.entryId)) map.set(a.entryId, a);
        }
        return map;
    }, [attachmentAnalyses]);

    const docTypeOptions = useMemo(
        () =>
            [...new Set(attachmentAnalyses.map(a => a.documentType).filter(Boolean))]
                .sort()
                .map(v => ({ value: v!, label: v! })),
        [attachmentAnalyses]
    );

    const matchStatusOptions = [
        { value: "all_match", label: "All match" },
        { value: "has_mismatch", label: "Has mismatch" },
        { value: "has_error", label: "Has error" },
    ];

    // Sorting
    const { sortKey, sortDir, toggleSort, sortFn } = useSort<Entry>("date", "asc");

    // Apply client-side filters + sort
    const filtered = useMemo(() => {
        const searchLower = search.toLowerCase();
        const result = entries.filter(e => {
            if (selectedSubcategories.length > 0 && !selectedSubcategories.includes(e.subcategory)) return false;
            if (searchLower && !e.description.toLowerCase().includes(searchLower)) return false;

            const a = analysisByEntry.get(e.id);
            if (selectedDocTypes.length > 0 && (!a || !selectedDocTypes.includes(a.documentType || ""))) {
                return false;
            }
            if (selectedDocMatchStatus.length > 0) {
                if (!a) return false;
                const allMatch = a.amountMatch !== false && a.vendorMatch !== false && a.dateMatch !== false;
                const hasMismatch = a.amountMatch === false || a.vendorMatch === false || a.dateMatch === false;
                const hasError = !!a.error;
                const passes = selectedDocMatchStatus.some(s => {
                    if (s === "all_match") return allMatch && !hasError;
                    if (s === "has_mismatch") return hasMismatch;
                    if (s === "has_error") return hasError;
                    return false;
                });
                if (!passes) return false;
            }
            return true;
        });
        return sortFn(result, {
            date: e => e.date,
            description: e => e.description.toLowerCase(),
            category: e => e.category,
            subcategory: e => e.subcategory,
            amount: e => e.amount,
            unit: e => e.unitCode || "",
        });
    }, [entries, selectedSubcategories, search, selectedDocTypes, selectedDocMatchStatus, analysisByEntry, sortFn]);

    // Financial totals
    const totals = useMemo(() => {
        let revenue = 0;
        let expenses = 0;
        for (const e of filtered) {
            if (e.movementType === "C") revenue += e.amount;
            else expenses += e.amount;
        }
        return { revenue, expenses, net: revenue - expenses, count: filtered.length };
    }, [filtered]);

    // Period attachment-health summary (over the period-scoped analyses)
    const docSummary = useMemo(() => {
        const analyzed = attachmentAnalyses.filter(a => !a.error);
        return {
            total: attachmentAnalyses.length,
            errors: attachmentAnalyses.length - analyzed.length,
            amountBad: analyzed.filter(a => a.amountMatch === false).length,
            vendorBad: analyzed.filter(a => a.vendorMatch === false).length,
            dateBad: analyzed.filter(a => a.dateMatch === false).length,
        };
    }, [attachmentAnalyses]);

    // Virtualizer
    const parentRef = useRef<HTMLDivElement>(null);
    const virtualizer = useVirtualizer({
        count: filtered.length,
        getScrollElement: () => parentRef.current,
        estimateSize: () => 36,
        overscan: 20,
    });

    // Deep link: once the target period's entries + analyses have loaded, scroll/highlight the
    // entry row and auto-open its attachment-analysis dialog. Runs once per (period|entry) set.
    useEffect(() => {
        if (!deepLinkEntry || loading) return;
        // Wait until the period state matches the deep-link period (data is then for it).
        if (deepLinkPeriod && selectedPeriod !== deepLinkPeriod) return;
        const key = `${deepLinkPeriod ?? ""}|${deepLinkEntry}`;
        if (deepLinkHandledRef.current === key) return;
        deepLinkHandledRef.current = key;

        const idx = filtered.findIndex(e => e.id === deepLinkEntry);
        if (idx >= 0) {
            virtualizer.scrollToIndex(idx, { align: "center" });
            setHighlightedEntryId(deepLinkEntry);
        }
        // Open the validation dialog when an analysis exists for the entry (FR-007); when the
        // entry has no analysis we still scrolled/highlighted above — no dialog, no error (FR-008).
        const analysis = analysisByEntry.get(deepLinkEntry);
        if (analysis) setSelectedAnalysis(analysis);
    }, [deepLinkEntry, deepLinkPeriod, loading, selectedPeriod, filtered, analysisByEntry, virtualizer]);

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

                <Card>
                    <CardContent className="p-3 space-y-3">
                        <div className="space-y-1.5">
                            <span className="block text-xs font-medium text-muted-foreground">Document type</span>
                            <MultiSelect
                                options={docTypeOptions}
                                selected={selectedDocTypes}
                                onSelectedChange={setSelectedDocTypes}
                                placeholder="All"
                                className="w-full"
                            />
                        </div>
                        <div className="space-y-1.5">
                            <span className="block text-xs font-medium text-muted-foreground">Attachment status</span>
                            <MultiSelect
                                options={matchStatusOptions}
                                selected={selectedDocMatchStatus}
                                onSelectedChange={setSelectedDocMatchStatus}
                                placeholder="All"
                                className="w-full"
                            />
                        </div>
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
                    <div className="flex items-center justify-between gap-4 flex-wrap">
                        <CardTitle className="flex items-center gap-2 text-xl">
                            <Receipt className="h-5 w-5" />
                            Entries
                        </CardTitle>
                        <div className="flex items-center gap-3 text-sm flex-wrap">
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
                                    {docSummary.total > 0 && (
                                        <>
                                            <div className="w-px h-4 bg-border" />
                                            <span className="text-xs text-muted-foreground">
                                                {docSummary.total} docs
                                            </span>
                                            {docSummary.amountBad > 0 && (
                                                <Badge variant="destructive">{docSummary.amountBad} amount</Badge>
                                            )}
                                            {docSummary.vendorBad > 0 && (
                                                <Badge variant="destructive">{docSummary.vendorBad} vendor</Badge>
                                            )}
                                            {docSummary.dateBad > 0 && (
                                                <Badge variant="outline" className="border-yellow-400 text-yellow-700">
                                                    {docSummary.dateBad} date
                                                </Badge>
                                            )}
                                            {docSummary.errors > 0 && (
                                                <Badge variant="secondary">{docSummary.errors} errors</Badge>
                                            )}
                                        </>
                                    )}
                                </>
                            )}
                        </div>
                    </div>
                </CardHeader>
                <CardContent className="flex-1 flex flex-col min-h-0 pt-0">
                    <div className="rounded-md border flex-1 flex flex-col min-h-0">
                        <div className="flex bg-muted/50 text-xs font-medium text-muted-foreground border-b shrink-0">
                            <div className="w-[80px] px-2 py-2 shrink-0">
                                <SortableHeader
                                    label="Date"
                                    sortKey="date"
                                    currentSort={sortKey}
                                    currentDirection={sortDir}
                                    onSort={toggleSort}
                                />
                            </div>
                            <div className="flex-1 px-2 py-2 min-w-0">
                                <SortableHeader
                                    label="Description"
                                    sortKey="description"
                                    currentSort={sortKey}
                                    currentDirection={sortDir}
                                    onSort={toggleSort}
                                />
                            </div>
                            <div className="w-[120px] px-2 py-2 shrink-0">
                                <SortableHeader
                                    label="Category"
                                    sortKey="category"
                                    currentSort={sortKey}
                                    currentDirection={sortDir}
                                    onSort={toggleSort}
                                />
                            </div>
                            <div className="w-[120px] px-2 py-2 shrink-0">
                                <SortableHeader
                                    label="Subcategory"
                                    sortKey="subcategory"
                                    currentSort={sortKey}
                                    currentDirection={sortDir}
                                    onSort={toggleSort}
                                />
                            </div>
                            <div className="w-[56px] px-2 py-2 shrink-0">
                                <SortableHeader
                                    label="Unit"
                                    sortKey="unit"
                                    currentSort={sortKey}
                                    currentDirection={sortDir}
                                    onSort={toggleSort}
                                />
                            </div>
                            <div className="w-[64px] px-2 py-2 shrink-0">Doc</div>
                            <div className="w-[40px] px-1 py-2 shrink-0 text-center">Amt</div>
                            <div className="w-[40px] px-1 py-2 shrink-0 text-center">Vnd</div>
                            <div className="w-[40px] px-1 py-2 shrink-0 text-center">Dt</div>
                            <div className="w-[110px] px-2 py-2 shrink-0 flex justify-end">
                                <SortableHeader
                                    label="Amount"
                                    sortKey="amount"
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
                                    const analysis = analysisByEntry.get(entry.id);
                                    const docLabel = analysis
                                        ? analysis.error
                                            ? "error"
                                            : analysis.documentType || "doc"
                                        : null;
                                    const isHighlighted = highlightedEntryId === entry.id;
                                    return (
                                        <div
                                            key={entry.id}
                                            className={`flex items-center border-b border-border/50 hover:bg-muted/30 text-sm absolute w-full ${
                                                analysis ? "cursor-pointer" : ""
                                            } ${isHighlighted ? "bg-yellow-100 ring-1 ring-inset ring-yellow-400" : ""}`}
                                            style={{
                                                height: `${virtualRow.size}px`,
                                                transform: `translateY(${virtualRow.start}px)`,
                                            }}
                                            title={
                                                analysis
                                                    ? analysis.serviceDescription ||
                                                      analysis.error ||
                                                      "Click for attachment detail"
                                                    : undefined
                                            }
                                            onClick={analysis ? () => setSelectedAnalysis(analysis) : undefined}
                                        >
                                            <div className="w-[80px] px-2 shrink-0 whitespace-nowrap">
                                                {formatDate(entry.date)}
                                            </div>
                                            <div className="flex-1 px-2 min-w-0 truncate" title={entry.description}>
                                                {stripDescriptionPrefix(entry.description, entry.subcategory)}
                                            </div>
                                            <div
                                                className="w-[120px] px-2 shrink-0 text-muted-foreground truncate text-xs"
                                                title={entry.category}
                                            >
                                                {entry.category}
                                            </div>
                                            <div
                                                className="w-[120px] px-2 shrink-0 text-muted-foreground truncate text-xs"
                                                title={entry.subcategory}
                                            >
                                                {entry.subcategory}
                                            </div>
                                            <div className="w-[56px] px-2 shrink-0 text-muted-foreground text-xs">
                                                {entry.unitCode || "-"}
                                            </div>
                                            <div
                                                className={`w-[64px] px-2 shrink-0 truncate text-xs ${
                                                    analysis?.error ? "text-red-600" : "text-muted-foreground"
                                                }`}
                                                title={docLabel || undefined}
                                            >
                                                {docLabel || "—"}
                                            </div>
                                            <div className="w-[40px] px-1 shrink-0 flex justify-center">
                                                {analysis ? <MatchCell match={analysis.amountMatch} /> : null}
                                            </div>
                                            <div className="w-[40px] px-1 shrink-0 flex justify-center">
                                                {analysis ? <MatchCell match={analysis.vendorMatch} /> : null}
                                            </div>
                                            <div className="w-[40px] px-1 shrink-0 flex justify-center">
                                                {analysis ? <MatchCell match={analysis.dateMatch} /> : null}
                                            </div>
                                            <div
                                                className={`w-[110px] px-2 shrink-0 text-right tabular-nums ${
                                                    entry.movementType === "D" ? "text-red-600" : "text-green-600"
                                                }`}
                                            >
                                                {formatCurrency(entry.amount)}
                                            </div>
                                        </div>
                                    );
                                })}
                            </div>
                        </div>

                        {/* Footer */}
                        {!loading && filtered.length > 0 && (
                            <div className="flex items-center border-t bg-muted/50 text-sm font-medium shrink-0">
                                <div className="w-[80px] px-2 py-2 shrink-0" />
                                <div className="flex-1 px-2 py-2 min-w-0 text-xs text-muted-foreground">Total</div>
                                <div className="w-[120px] px-2 py-2 shrink-0" />
                                <div className="w-[120px] px-2 py-2 shrink-0" />
                                <div className="w-[56px] px-2 py-2 shrink-0 text-right text-xs text-muted-foreground">
                                    {totals.count}
                                </div>
                                <div className="w-[64px] px-2 py-2 shrink-0" />
                                <div className="w-[40px] px-1 py-2 shrink-0" />
                                <div className="w-[40px] px-1 py-2 shrink-0" />
                                <div className="w-[40px] px-1 py-2 shrink-0" />
                                <div className="w-[110px] px-2 py-2 shrink-0 text-right tabular-nums font-semibold">
                                    {formatCurrency(totals.net)}
                                </div>
                            </div>
                        )}
                    </div>
                </CardContent>
            </Card>

            <AttachmentAnalysisDetailDialog
                analysis={selectedAnalysis}
                onOpenChange={open => {
                    if (!open) setSelectedAnalysis(null);
                }}
            />
        </div>
    );
}
