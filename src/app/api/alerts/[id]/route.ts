import { initAuth } from "@/auth";
import { getDb } from "@/db";
import {
    alerts,
    entries,
    accountabilityReports,
    subcategories,
    categories,
    vendors,
    units,
    attachments,
    attachmentAnalyses,
    documents,
    documentEntries,
} from "@/db/fiscal.schema";
import { eq, inArray, sql } from "drizzle-orm";
import { headers } from "next/headers";
import { type NextRequest, NextResponse } from "next/server";

const ALLOWED_ROLES = ["admin", "member"];

/**
 * Entry ids an alert concerns, parsed from its (untyped JSON) metadata: `entry_ids` array
 * (duplicate_entry, negative_credit, …) or a single `entry_id` (attachment_* mismatches).
 * Parses defensively — malformed/absent metadata yields no ids. (Server-side twin of the
 * client helper in dashboard/alerts/alerts.tsx; kept here to avoid importing a React module.)
 */
function affectedEntryIds(metadata: string | null): string[] {
    if (!metadata) return [];
    try {
        const meta = JSON.parse(metadata) as { entry_ids?: unknown; entry_id?: unknown };
        if (Array.isArray(meta.entry_ids)) return meta.entry_ids.filter((v): v is string => typeof v === "string");
        if (typeof meta.entry_id === "string") return [meta.entry_id];
        return [];
    } catch {
        return [];
    }
}

// Full alert projection shared by GET and PATCH so both return a complete object.
const alertColumns = {
    id: alerts.id,
    type: alerts.type,
    severity: alerts.severity,
    title: alerts.title,
    description: alerts.description,
    referencePeriod: alerts.referencePeriod,
    createdAt: alerts.createdAt,
    resolved: alerts.resolved,
    resolvedAt: alerts.resolvedAt,
    notes: alerts.notes,
    metadata: alerts.metadata,
};

export async function GET(_request: NextRequest, { params }: { params: Promise<{ id: string }> }) {
    const authInstance = await initAuth();
    const session = await authInstance.api.getSession({ headers: await headers() });
    const userRole = (session?.user as { role?: string } | undefined)?.role;
    if (!session || !userRole || !ALLOWED_ROLES.includes(userRole)) {
        return NextResponse.json({ error: "Unauthorized" }, { status: 403 });
    }

    const { id } = await params;
    const db = await getDb();

    const row = (await db.select(alertColumns).from(alerts).where(eq(alerts.id, id)).limit(1))[0];
    if (!row) {
        return NextResponse.json({ error: "Alert not found" }, { status: 404 });
    }

    // Resolve the affected entry ids (from metadata) into full entry detail rows so the detail page
    // can show each entry inline rather than as a bare link. Joins mirror GET /api/entries.
    const entryIds = affectedEntryIds(row.metadata);
    const entryRows = entryIds.length
        ? await db
              .select({
                  entryId: entries.id,
                  period: accountabilityReports.period,
                  date: entries.date,
                  description: entries.description,
                  amount: entries.amount,
                  movementType: entries.movementType,
                  category: categories.name,
                  subcategory: subcategories.name,
                  vendor: vendors.name,
                  unitCode: units.code,
              })
              .from(entries)
              .innerJoin(accountabilityReports, eq(entries.reportId, accountabilityReports.id))
              .innerJoin(subcategories, eq(entries.subcategoryId, subcategories.id))
              .innerJoin(categories, eq(subcategories.categoryId, categories.id))
              .leftJoin(vendors, eq(entries.vendorId, vendors.id))
              .leftJoin(units, eq(entries.unitId, units.id))
              .where(inArray(entries.id, entryIds))
              .orderBy(accountabilityReports.period, entries.date)
        : [];

    // Each affected entry's attachment analysis (same shape as GET /api/attachment-analyses, so the
    // entries-view detail modal can consume it directly and self-fetch its page images by `id`).
    const analysisRows = entryIds.length
        ? await db
              .select({
                  id: attachmentAnalyses.id,
                  attachmentId: attachmentAnalyses.attachmentId,
                  analyzedAt: attachmentAnalyses.analyzedAt,
                  documentType: attachmentAnalyses.documentType,
                  extractedAmount: attachmentAnalyses.extractedAmount,
                  amountMatch: attachmentAnalyses.amountMatch,
                  extractedCnpj: attachmentAnalyses.extractedCnpj,
                  issuerName: attachmentAnalyses.issuerName,
                  vendorMatch: attachmentAnalyses.vendorMatch,
                  extractedDate: attachmentAnalyses.extractedDate,
                  dateMatch: attachmentAnalyses.dateMatch,
                  documentNumber: attachmentAnalyses.documentNumber,
                  serviceDescription: attachmentAnalyses.serviceDescription,
                  error: attachmentAnalyses.error,
                  entryId: sql<string>`${entries.id}`.as("entry_id"),
                  entryDate: entries.date,
                  entryDescription: entries.description,
                  entryAmount: entries.amount,
                  entryMovementType: entries.movementType,
                  vendorName: vendors.name,
                  subcategoryName: subcategories.name,
                  categoryName: categories.name,
              })
              .from(attachmentAnalyses)
              .innerJoin(attachments, eq(attachmentAnalyses.attachmentId, attachments.id))
              .innerJoin(entries, eq(attachments.entryId, entries.id))
              .leftJoin(subcategories, eq(entries.subcategoryId, subcategories.id))
              .leftJoin(categories, eq(subcategories.categoryId, categories.id))
              .leftJoin(vendors, eq(entries.vendorId, vendors.id))
              .where(inArray(attachments.entryId, entryIds))
        : [];
    const analysisByEntry = new Map(analysisRows.map(a => [a.entryId, a]));

    // The real documents linked to each affected entry (for the per-entry "documents" modal).
    const docRows = entryIds.length
        ? await db
              .select({
                  entryId: documentEntries.entryId,
                  id: documents.id,
                  documentNumber: documents.documentNumber,
                  issuerName: documents.issuerName,
                  documentType: documents.documentType,
                  totalValue: documents.totalValue,
              })
              .from(documentEntries)
              .innerJoin(documents, eq(documentEntries.documentId, documents.id))
              .where(inArray(documentEntries.entryId, entryIds))
        : [];
    const docsByEntry = new Map<string, Array<Omit<(typeof docRows)[number], "entryId">>>();
    for (const d of docRows) {
        const { entryId, ...doc } = d;
        const list = docsByEntry.get(entryId) ?? [];
        list.push(doc);
        docsByEntry.set(entryId, list);
    }

    const enrichedEntries = entryRows.map(e => ({
        ...e,
        analysis: analysisByEntry.get(e.entryId) ?? null,
        documents: docsByEntry.get(e.entryId) ?? [],
    }));

    return NextResponse.json({ ...row, entries: enrichedEntries });
}

export async function PATCH(request: NextRequest, { params }: { params: Promise<{ id: string }> }) {
    const authInstance = await initAuth();
    const session = await authInstance.api.getSession({ headers: await headers() });
    const userRole = (session?.user as { role?: string } | undefined)?.role;
    if (!session || !userRole || !ALLOWED_ROLES.includes(userRole)) {
        return NextResponse.json({ error: "Unauthorized" }, { status: 403 });
    }

    const { id } = await params;
    const body = await request.json();
    const { resolved, notes } = body as { resolved: boolean; notes?: string };

    const db = await getDb();

    await db
        .update(alerts)
        .set({
            resolved,
            resolvedAt: resolved ? new Date() : null,
            notes: notes ?? null,
        })
        .where(eq(alerts.id, id));

    const updated = await db.select(alertColumns).from(alerts).where(eq(alerts.id, id)).limit(1);

    if (updated.length === 0) {
        return NextResponse.json({ error: "Alert not found" }, { status: 404 });
    }

    return NextResponse.json(updated[0]);
}
