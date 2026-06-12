"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { ArrowLeft, ExternalLink, AlertTriangle, FileText, Paperclip, Files } from "lucide-react";
import { evidenceFields, referencedDocumentId, SeverityBadge, StatusBadge } from "../alerts";
import AttachmentAnalysisDetailDialog from "../../entries/AttachmentAnalysisDetailDialog";
import type { AttachmentAnalysisRow } from "../../entries/types";

interface AttachedDocument {
    id: string;
    documentNumber: string;
    issuerName: string | null;
    documentType: string | null;
    totalValue: number | null;
}

interface AffectedEntry {
    entryId: string;
    period: string;
    date: string;
    description: string;
    amount: number;
    movementType: string;
    category: string | null;
    subcategory: string | null;
    vendor: string | null;
    unitCode: string | null;
    analysis: AttachmentAnalysisRow | null;
    documents: AttachedDocument[];
}

interface AlertDetail {
    id: string;
    type: string;
    severity: string;
    title: string;
    description: string;
    referencePeriod: string;
    createdAt: number;
    resolved: boolean;
    resolvedAt: number | null;
    notes: string | null;
    metadata: string | null;
    entries: AffectedEntry[];
}

function formatTimestamp(ms: number | null): string {
    if (!ms) return "—";
    return new Date(ms).toLocaleString("pt-BR");
}

function formatCurrency(value: number): string {
    return value.toLocaleString("pt-BR", { style: "currency", currency: "BRL" });
}

function Field({ label, value }: { label: string; value: string }) {
    return (
        <div className="flex flex-col gap-0.5">
            <span className="text-[10px] uppercase tracking-wide text-muted-foreground">{label}</span>
            <span className="text-sm">{value}</span>
        </div>
    );
}

export default function AlertDetailClient({ alertId }: { alertId: string }) {
    const [alert, setAlert] = useState<AlertDetail | null>(null);
    const [loading, setLoading] = useState(true);
    const [notFound, setNotFound] = useState(false);
    const [error, setError] = useState<string | null>(null);

    // Resolve/reopen control state
    const [notesDraft, setNotesDraft] = useState("");
    const [saving, setSaving] = useState(false);
    const [actionError, setActionError] = useState<string | null>(null);

    // Per-entry modals: the entries-view attachment analysis dialog, and an attached-documents list.
    const [selectedAnalysis, setSelectedAnalysis] = useState<AttachmentAnalysisRow | null>(null);
    const [docsEntry, setDocsEntry] = useState<AffectedEntry | null>(null);

    useEffect(() => {
        let cancelled = false;
        setLoading(true);
        setNotFound(false);
        setError(null);
        fetch(`/api/alerts/${alertId}`)
            .then(res => {
                if (res.status === 404) {
                    if (!cancelled) setNotFound(true);
                    return null;
                }
                if (!res.ok) throw new Error("Failed to fetch alert");
                return res.json();
            })
            .then((data: AlertDetail | null) => {
                if (!cancelled && data) {
                    setAlert(data);
                    setNotesDraft(data.notes ?? "");
                }
            })
            .catch(e => {
                if (!cancelled) setError(e.message);
            })
            .finally(() => {
                if (!cancelled) setLoading(false);
            });
        return () => {
            cancelled = true;
        };
    }, [alertId]);

    const submitResolution = async (resolved: boolean) => {
        if (!alert) return;
        setSaving(true);
        setActionError(null);
        try {
            const res = await fetch(`/api/alerts/${alert.id}`, {
                method: "PATCH",
                headers: { "Content-Type": "application/json" },
                // Reopening clears notes; resolving keeps the (optional) draft.
                body: JSON.stringify({ resolved, notes: resolved ? notesDraft.trim() || null : null }),
            });
            if (!res.ok) throw new Error("Failed to update alert");
            // PATCH returns the alert core fields (no entries); preserve the entries we already have.
            const updated: Omit<AlertDetail, "entries"> = await res.json();
            setAlert(prev => (prev ? { ...prev, ...updated } : { ...updated, entries: [] }));
            setNotesDraft(updated.notes ?? "");
        } catch (e) {
            setActionError((e as Error).message);
        } finally {
            setSaving(false);
        }
    };

    const backLink = (
        <Link
            href="/dashboard/alerts"
            className="inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground"
        >
            <ArrowLeft className="h-4 w-4" /> Back to alerts
        </Link>
    );

    if (loading) {
        return (
            <div className="space-y-4">
                {backLink}
                <Card>
                    <CardContent className="py-12 text-center text-muted-foreground">Loading…</CardContent>
                </Card>
            </div>
        );
    }

    if (notFound) {
        return (
            <div className="space-y-4">
                {backLink}
                <Card>
                    <CardContent className="py-12 text-center text-muted-foreground">Alert not found.</CardContent>
                </Card>
            </div>
        );
    }

    if (error || !alert) {
        return (
            <div className="space-y-4">
                {backLink}
                <Card>
                    <CardContent className="py-12 text-center text-red-500">
                        Error: {error ?? "Unknown error"}
                    </CardContent>
                </Card>
            </div>
        );
    }

    const docId = referencedDocumentId(alert.metadata);
    const evidence = evidenceFields(alert.metadata);

    return (
        <div className="flex-1 space-y-4 overflow-auto">
            {backLink}

            {/* Header + core fields */}
            <Card>
                <CardHeader className="pb-3">
                    <CardTitle className="flex flex-wrap items-center gap-2 text-xl">
                        <AlertTriangle className="h-5 w-5" />
                        {alert.title}
                        <SeverityBadge severity={alert.severity} />
                        <StatusBadge resolved={alert.resolved} />
                    </CardTitle>
                </CardHeader>
                <CardContent className="space-y-4">
                    <div className="grid grid-cols-2 gap-x-6 gap-y-2 text-sm sm:grid-cols-3">
                        <Field label="Type" value={alert.type} />
                        <Field label="Period" value={alert.referencePeriod} />
                        <Field label="Created" value={formatTimestamp(alert.createdAt)} />
                        <Field label="Resolved at" value={formatTimestamp(alert.resolvedAt)} />
                    </div>
                    <div className="space-y-1">
                        <span className="text-[10px] uppercase tracking-wide text-muted-foreground">Description</span>
                        <p className="whitespace-pre-wrap text-sm">{alert.description}</p>
                    </div>
                    {alert.notes && (
                        <div className="space-y-1">
                            <span className="text-[10px] uppercase tracking-wide text-muted-foreground">Notes</span>
                            <p className="whitespace-pre-wrap text-sm">{alert.notes}</p>
                        </div>
                    )}
                </CardContent>
            </Card>

            {/* Resolution */}
            <Card>
                <CardHeader className="pb-3">
                    <CardTitle className="text-base">Resolution</CardTitle>
                </CardHeader>
                <CardContent className="space-y-3">
                    {alert.resolved ? (
                        <div className="flex flex-col gap-3">
                            <p className="text-sm text-muted-foreground">
                                This alert is resolved
                                {alert.resolvedAt ? ` (${formatTimestamp(alert.resolvedAt)})` : ""}.
                            </p>
                            <Button variant="outline" disabled={saving} onClick={() => submitResolution(false)}>
                                {saving ? "Reopening…" : "Reopen alert"}
                            </Button>
                        </div>
                    ) : (
                        <div className="flex flex-col gap-3">
                            <div className="space-y-1">
                                <label className="text-xs text-muted-foreground">Notes (optional)</label>
                                <Textarea
                                    value={notesDraft}
                                    onChange={e => setNotesDraft(e.target.value)}
                                    placeholder="Why is this resolved? (optional)"
                                    rows={3}
                                />
                            </div>
                            <Button disabled={saving} onClick={() => submitResolution(true)}>
                                {saving ? "Resolving…" : "Resolve alert"}
                            </Button>
                        </div>
                    )}
                    {actionError && <p className="text-sm text-red-600">Error: {actionError}</p>}
                </CardContent>
            </Card>

            {/* Evidence (structured metadata) + document cross-link */}
            {(evidence.length > 0 || docId) && (
                <Card>
                    <CardHeader className="pb-3">
                        <CardTitle className="text-base">Evidence</CardTitle>
                    </CardHeader>
                    <CardContent className="space-y-3">
                        {evidence.length > 0 && (
                            <div className="grid grid-cols-2 gap-x-6 gap-y-2 sm:grid-cols-3">
                                {evidence.map(f => (
                                    <Field key={f.key} label={f.label} value={f.value} />
                                ))}
                            </div>
                        )}
                        {docId && (
                            <Link
                                href={`/dashboard/documents/${docId}`}
                                className="inline-flex items-center gap-1 text-sm text-blue-600 hover:underline"
                            >
                                <FileText className="h-4 w-4" /> View referenced document{" "}
                                <ExternalLink className="h-3 w-3" />
                            </Link>
                        )}
                    </CardContent>
                </Card>
            )}

            {/* Affected entries — full detail per entry, not just a link */}
            <Card>
                <CardHeader className="pb-3">
                    <CardTitle className="text-base">Affected entries ({alert.entries.length})</CardTitle>
                </CardHeader>
                <CardContent>
                    {alert.entries.length === 0 ? (
                        <p className="py-2 text-sm text-muted-foreground">No entries linked to this alert.</p>
                    ) : (
                        <div className="space-y-3">
                            {alert.entries.map(e => (
                                <div key={e.entryId} className="rounded-md border p-3 space-y-3">
                                    <div className="flex items-center gap-2 text-sm font-medium">
                                        <span className="tabular-nums">{e.date}</span>
                                        <span className="text-muted-foreground">·</span>
                                        <span className="truncate" title={e.description}>
                                            {e.description}
                                        </span>
                                    </div>
                                    <div className="grid grid-cols-2 gap-x-6 gap-y-2 text-sm sm:grid-cols-3">
                                        <Field label="Period" value={e.period} />
                                        <Field
                                            label="Amount"
                                            value={`${e.movementType === "C" ? "+" : "-"}${formatCurrency(e.amount)}`}
                                        />
                                        <Field label="Category" value={e.category ?? "—"} />
                                        <Field label="Subcategory" value={e.subcategory ?? "—"} />
                                        <Field label="Vendor" value={e.vendor ?? "—"} />
                                        <Field label="Unit" value={e.unitCode ?? "—"} />
                                    </div>
                                    <div className="flex flex-wrap gap-2">
                                        <Button
                                            size="sm"
                                            variant="outline"
                                            disabled={!e.analysis}
                                            onClick={() => e.analysis && setSelectedAnalysis(e.analysis)}
                                            title={
                                                e.analysis
                                                    ? "View the attachment and its page images"
                                                    : "No attachment analysis"
                                            }
                                        >
                                            <Paperclip className="h-3.5 w-3.5" /> View attachment
                                        </Button>
                                        <Button
                                            size="sm"
                                            variant="outline"
                                            disabled={e.documents.length === 0}
                                            onClick={() => setDocsEntry(e)}
                                        >
                                            <Files className="h-3.5 w-3.5" /> Documents ({e.documents.length})
                                        </Button>
                                    </div>
                                </div>
                            ))}
                        </div>
                    )}
                </CardContent>
            </Card>

            {/* Entries-view attachment analysis modal (page images + extracted fields). */}
            <AttachmentAnalysisDetailDialog
                analysis={selectedAnalysis}
                onOpenChange={open => !open && setSelectedAnalysis(null)}
            />

            {/* Per-entry attached-documents modal. */}
            <Dialog open={docsEntry !== null} onOpenChange={open => !open && setDocsEntry(null)}>
                <DialogContent className="max-w-lg">
                    <DialogHeader>
                        <DialogTitle className="flex items-center gap-2">
                            <Files className="h-4 w-4" /> Attached documents
                        </DialogTitle>
                    </DialogHeader>
                    {docsEntry && (
                        <div className="space-y-1">
                            {docsEntry.documents.length === 0 ? (
                                <p className="py-2 text-sm text-muted-foreground">No documents linked to this entry.</p>
                            ) : (
                                docsEntry.documents.map(d => (
                                    <Link
                                        key={d.id}
                                        href={`/dashboard/documents/${d.id}`}
                                        className="flex items-center justify-between gap-2 rounded px-2 py-2 text-sm hover:bg-muted"
                                    >
                                        <span className="min-w-0 truncate">
                                            <span className="font-medium tabular-nums">{d.documentNumber}</span>
                                            <span className="text-muted-foreground">
                                                {" "}
                                                · {d.issuerName ?? "—"}
                                                {d.documentType ? ` · ${d.documentType}` : ""}
                                            </span>
                                        </span>
                                        <span className="inline-flex shrink-0 items-center gap-1 text-blue-600">
                                            <FileText className="h-3.5 w-3.5" />
                                            <ExternalLink className="h-3 w-3" />
                                        </span>
                                    </Link>
                                ))
                            )}
                        </div>
                    )}
                </DialogContent>
            </Dialog>
        </div>
    );
}
