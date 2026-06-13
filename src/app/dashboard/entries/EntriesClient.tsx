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
import { Receipt, X } from "lucide-react";
import AttachmentAnalysisDetailDialog from "./AttachmentAnalysisDetailDialog";
import { shortenEntryId } from "./deepLink";
import { deepLinkView } from "./deeplinkView";
import type { Entry, AttachmentAnalysisRow } from "./types";
import { useTranslation, useLocale } from "@/lib/i18n/client";
import { formatCurrency, formatDate } from "@/lib/i18n/formatters.client";
import { plural } from "@/lib/i18n/plural";

// Feedback for a deep-link that could not land on its target row (feature 037 / issue #45).
type DeepLinkNotice = { kind: "not-found" | "invalid"; entryId: string; period: string };

function getCurrentPeriod(): string {
    const now = new Date();
    return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, "0")}`;
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
            <Badge
                variant="outline"
                className="border-green-400 dark:border-green-700 text-green-700 dark:text-green-400 text-[10px] px-1 py-0"
            >
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
    const t = useTranslation();
    const locale = useLocale();
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
    // Non-blocking feedback when the deep-link can't land (entry absent or invalid id).
    const [deepLinkNotice, setDeepLinkNotice] = useState<DeepLinkNotice | null>(null);
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

    // Reset client-side filters when period changes; a manual period change also clears any
    // stale deep-link notice so it doesn't linger against an unrelated period (FR-009).
    const handlePeriodChange = (value: string) => {
        setSelectedPeriod(value);
        setSelectedSubcategories([]);
        setSearch("");
        setSelectedDocTypes([]);
        setSelectedDocMatchStatus([]);
        setDeepLinkNotice(null);
    };

    // Manual filter handlers: clear a stale deep-link notice when the user adjusts a filter
    // themselves (FR-009). The programmatic filter-recovery reset (in the deep-link effect) uses
    // the raw setters directly, so it does NOT clear the notice through these.
    const handleSubcategoriesChange = (v: string[]) => {
        setSelectedSubcategories(v);
        setDeepLinkNotice(null);
    };
    const handleSearchChange = (v: string) => {
        setSearch(v);
        setDeepLinkNotice(null);
    };
    const handleDocTypesChange = (v: string[]) => {
        setSelectedDocTypes(v);
        setDeepLinkNotice(null);
    };
    const handleDocMatchStatusChange = (v: string[]) => {
        setSelectedDocMatchStatus(v);
        setDeepLinkNotice(null);
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
        { value: "all_match", label: t("match.all_match") },
        { value: "has_mismatch", label: t("match.has_mismatch") },
        { value: "has_error", label: t("match.has_error") },
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

    // Deep link: once the target period's entries + analyses have loaded, resolve the target row
    // and act on the outcome (feature 037 / issue #45). Runs once per (period|entry) set — except
    // a transitional filter-recovery, which intentionally does NOT consume the link so the
    // post-clear re-render can land on the now-visible row.
    useEffect(() => {
        if (!deepLinkEntry || loading) return;
        // Wait until the period state matches the deep-link period (data is then for it).
        if (deepLinkPeriod && selectedPeriod !== deepLinkPeriod) return;
        const key = `${deepLinkPeriod ?? ""}|${deepLinkEntry}`;
        if (deepLinkHandledRef.current === key) return;

        const hasActiveFilter =
            selectedSubcategories.length > 0 ||
            search.length > 0 ||
            selectedDocTypes.length > 0 ||
            selectedDocMatchStatus.length > 0;
        const analysis = analysisByEntry.get(deepLinkEntry);
        // Pure outcome→action mapping (feature 045 / TEST-003). The period-load gate above already
        // ensures the data is for the deep-link period, so selectPeriod is a no-op here (selected
        // === param) — the view drives recovery / highlight / dialog / notice / consumption.
        const view = deepLinkView({
            entryId: deepLinkEntry,
            paramPeriod: selectedPeriod,
            selectedPeriod,
            hasActiveFilter,
            presentUnfiltered: entries.some(e => e.id === deepLinkEntry),
            filteredIndex: filtered.findIndex(e => e.id === deepLinkEntry),
            hasAnalysis: analysis !== undefined,
        });

        // Filter-recovery is transitional: clear the filters and let the effect re-run (filtered
        // changes) to find the now-visible row. Don't consume the link or strip the URL yet.
        if (view.clearFilters) {
            setSelectedSubcategories([]);
            setSearch("");
            setSelectedDocTypes([]);
            setSelectedDocMatchStatus([]);
            return;
        }

        // Terminal outcomes consume the link and strip the params so a refresh won't re-trigger.
        deepLinkHandledRef.current = key;
        const loadedPeriod = selectedPeriod;
        if (view.highlightIndex !== undefined) {
            virtualizer.scrollToIndex(view.highlightIndex, { align: "center" });
            setHighlightedEntryId(deepLinkEntry);
            // Open the validation dialog when an analysis exists for the entry (FR-008); when the
            // entry has no analysis we still scrolled/highlighted above — no dialog, no notice.
            if (view.openDialog && analysis) setSelectedAnalysis(analysis);
        } else if (view.notice) {
            // "not-found" or "invalid" — surface a non-blocking notice instead of failing silently.
            setDeepLinkNotice({ kind: view.notice.kind, entryId: deepLinkEntry, period: loadedPeriod });
        }
        // Strip the consumed entry/period params from the URL so a refresh doesn't re-trigger the
        // deep-link behavior (FR-007); selected period is preserved in component state (A4).
        if (typeof window !== "undefined") {
            const url = new URL(window.location.href);
            url.searchParams.delete("entry");
            url.searchParams.delete("period");
            const qs = url.searchParams.toString();
            window.history.replaceState(null, "", `${url.pathname}${qs ? `?${qs}` : ""}`);
        }
    }, [
        deepLinkEntry,
        deepLinkPeriod,
        loading,
        selectedPeriod,
        entries,
        filtered,
        analysisByEntry,
        virtualizer,
        selectedSubcategories,
        search,
        selectedDocTypes,
        selectedDocMatchStatus,
    ]);

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
                <Card>
                    <CardContent className="p-3 space-y-2">
                        <span className="text-xs font-medium text-muted-foreground">{t("filter.period")}</span>
                        <Select value={selectedPeriod} onValueChange={handlePeriodChange}>
                            <SelectTrigger className="h-9">
                                <SelectValue placeholder={t("form.select_period")} />
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
                        <span className="text-xs font-medium text-muted-foreground">{t("filter.search")}</span>
                        <Input
                            placeholder={t("form.search_placeholder")}
                            value={search}
                            onChange={e => handleSearchChange(e.target.value)}
                            className="h-9"
                        />
                    </CardContent>
                </Card>

                <Card>
                    <CardContent className="p-3 space-y-3">
                        <div className="space-y-1.5">
                            <span className="block text-xs font-medium text-muted-foreground">
                                {t("filter.document_type")}
                            </span>
                            <MultiSelect
                                options={docTypeOptions}
                                selected={selectedDocTypes}
                                onSelectedChange={handleDocTypesChange}
                                placeholder={t("form.all")}
                                className="w-full"
                            />
                        </div>
                        <div className="space-y-1.5">
                            <span className="block text-xs font-medium text-muted-foreground">
                                {t("filter.attachment_status")}
                            </span>
                            <MultiSelect
                                options={matchStatusOptions}
                                selected={selectedDocMatchStatus}
                                onSelectedChange={handleDocMatchStatusChange}
                                placeholder={t("form.all")}
                                className="w-full"
                            />
                        </div>
                    </CardContent>
                </Card>

                <CategoryTree
                    data={entries}
                    selected={selectedSubcategories}
                    onSelectedChange={handleSubcategoriesChange}
                />
            </div>

            {/* Main content */}
            <Card className="flex-1 flex flex-col min-h-0">
                <CardHeader className="pb-3">
                    <div className="flex items-center justify-between gap-4 flex-wrap">
                        <CardTitle className="flex items-center gap-2 text-xl">
                            <Receipt className="h-5 w-5" />
                            {t("page.entries_title")}
                        </CardTitle>
                        <div className="flex items-center gap-3 text-sm flex-wrap">
                            <span className="text-muted-foreground">
                                {loading
                                    ? t("form.loading")
                                    : `${filtered.length} ${plural(t, "count.entries", filtered.length)}`}
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
                                    {docSummary.total > 0 && (
                                        <>
                                            <div className="w-px h-4 bg-border" />
                                            <span className="text-xs text-muted-foreground">
                                                {docSummary.total} {t("match.docs")}
                                            </span>
                                            {docSummary.amountBad > 0 && (
                                                <Badge variant="destructive">
                                                    {docSummary.amountBad} {t("match.amount")}
                                                </Badge>
                                            )}
                                            {docSummary.vendorBad > 0 && (
                                                <Badge variant="destructive">
                                                    {docSummary.vendorBad} {t("match.vendor")}
                                                </Badge>
                                            )}
                                            {docSummary.dateBad > 0 && (
                                                <Badge
                                                    variant="outline"
                                                    className="border-yellow-400 dark:border-yellow-700 text-yellow-700 dark:text-yellow-300"
                                                >
                                                    {docSummary.dateBad} {t("match.date")}
                                                </Badge>
                                            )}
                                            {docSummary.errors > 0 && (
                                                <Badge variant="secondary">
                                                    {docSummary.errors} {t("match.errors")}
                                                </Badge>
                                            )}
                                        </>
                                    )}
                                </>
                            )}
                        </div>
                    </div>
                </CardHeader>
                <CardContent className="flex-1 flex flex-col min-h-0 pt-0">
                    {deepLinkNotice && (
                        <div className="mb-2 flex items-start gap-2 rounded-md border border-amber-300 dark:border-amber-800 bg-amber-50 dark:bg-amber-950/40 px-3 py-2 text-sm text-amber-800 dark:text-amber-300">
                            <span className="flex-1">
                                {deepLinkNotice.kind === "invalid" ? (
                                    <>{t("notice.deeplink_invalid")}</>
                                ) : (
                                    <>
                                        {t("notice.deeplink_not_found_prefix")}{" "}
                                        <span className="font-mono">{shortenEntryId(deepLinkNotice.entryId)}</span> (
                                        {deepLinkNotice.period}) {t("notice.deeplink_not_found_suffix")}
                                    </>
                                )}
                            </span>
                            <button
                                type="button"
                                aria-label={t("action.dismiss")}
                                onClick={() => setDeepLinkNotice(null)}
                                className="shrink-0 rounded p-0.5 text-amber-700 dark:text-amber-300 hover:bg-amber-100 dark:hover:bg-amber-900/40"
                            >
                                <X className="h-4 w-4" />
                            </button>
                        </div>
                    )}
                    <div className="rounded-md border flex-1 flex flex-col min-h-0">
                        <div className="flex bg-muted/50 text-xs font-medium text-muted-foreground border-b shrink-0">
                            <div className="w-[80px] px-2 py-2 shrink-0">
                                <SortableHeader
                                    label={t("table.date")}
                                    sortKey="date"
                                    currentSort={sortKey}
                                    currentDirection={sortDir}
                                    onSort={toggleSort}
                                />
                            </div>
                            <div className="flex-1 px-2 py-2 min-w-0">
                                <SortableHeader
                                    label={t("table.description")}
                                    sortKey="description"
                                    currentSort={sortKey}
                                    currentDirection={sortDir}
                                    onSort={toggleSort}
                                />
                            </div>
                            <div className="w-[120px] px-2 py-2 shrink-0">
                                <SortableHeader
                                    label={t("table.category")}
                                    sortKey="category"
                                    currentSort={sortKey}
                                    currentDirection={sortDir}
                                    onSort={toggleSort}
                                />
                            </div>
                            <div className="w-[120px] px-2 py-2 shrink-0">
                                <SortableHeader
                                    label={t("table.subcategory")}
                                    sortKey="subcategory"
                                    currentSort={sortKey}
                                    currentDirection={sortDir}
                                    onSort={toggleSort}
                                />
                            </div>
                            <div className="w-[56px] px-2 py-2 shrink-0">
                                <SortableHeader
                                    label={t("table.unit")}
                                    sortKey="unit"
                                    currentSort={sortKey}
                                    currentDirection={sortDir}
                                    onSort={toggleSort}
                                />
                            </div>
                            <div className="w-[64px] px-2 py-2 shrink-0">{t("table.doc")}</div>
                            <div className="w-[40px] px-1 py-2 shrink-0 text-center">{t("table.amt")}</div>
                            <div className="w-[40px] px-1 py-2 shrink-0 text-center">{t("table.vnd")}</div>
                            <div className="w-[40px] px-1 py-2 shrink-0 text-center">{t("table.dt")}</div>
                            <div className="w-[110px] px-2 py-2 shrink-0 flex justify-end">
                                <SortableHeader
                                    label={t("table.amount")}
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
                                            ? t("badge.error")
                                            : analysis.documentType || t("list.doc_fallback")
                                        : null;
                                    const isHighlighted = highlightedEntryId === entry.id;
                                    return (
                                        <div
                                            key={entry.id}
                                            className={`flex items-center border-b border-border/50 hover:bg-muted/30 text-sm absolute w-full ${
                                                analysis ? "cursor-pointer" : ""
                                            } ${isHighlighted ? "bg-yellow-100 dark:bg-yellow-900/40 ring-1 ring-inset ring-yellow-400 dark:ring-yellow-600" : ""}`}
                                            style={{
                                                height: `${virtualRow.size}px`,
                                                transform: `translateY(${virtualRow.start}px)`,
                                            }}
                                            title={
                                                analysis
                                                    ? analysis.serviceDescription ||
                                                      analysis.error ||
                                                      t("list.open_attachment_detail")
                                                    : undefined
                                            }
                                            onClick={analysis ? () => setSelectedAnalysis(analysis) : undefined}
                                        >
                                            <div className="w-[80px] px-2 shrink-0 whitespace-nowrap">
                                                {formatDate(entry.date, locale)}
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
                                                    analysis?.error
                                                        ? "text-red-600 dark:text-red-400"
                                                        : "text-muted-foreground"
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
                                                    entry.movementType === "D"
                                                        ? "text-red-600 dark:text-red-400"
                                                        : "text-green-600 dark:text-green-400"
                                                }`}
                                            >
                                                {formatCurrency(entry.amount, locale)}
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
                                <div className="flex-1 px-2 py-2 min-w-0 text-xs text-muted-foreground">
                                    {t("summary.total")}
                                </div>
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
                                    {formatCurrency(totals.net, locale)}
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
