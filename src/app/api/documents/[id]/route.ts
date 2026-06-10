import { initAuth } from "@/auth";
import { getDb } from "@/db";
import {
    documents,
    documentEntries,
    entries,
    accountabilityReports,
    subcategories,
    categories,
    vendors,
    units,
    attachmentAnalyses,
} from "@/db/fiscal.schema";
import { documentStatus } from "@/lib/documents";
import { and, eq, inArray, ne, sql } from "drizzle-orm";
import { headers } from "next/headers";
import { NextResponse } from "next/server";

const ALLOWED_ROLES = ["admin", "member"];

export async function GET(_request: Request, { params }: { params: Promise<{ id: string }> }) {
    const authInstance = await initAuth();
    const session = await authInstance.api.getSession({ headers: await headers() });
    const userRole = (session?.user as { role?: string } | undefined)?.role;
    if (!session || !userRole || !ALLOWED_ROLES.includes(userRole)) {
        return NextResponse.json({ error: "Unauthorized" }, { status: 403 });
    }

    const { id } = await params;
    const db = await getDb();

    const doc = (await db.select().from(documents).where(eq(documents.id, id)).limit(1))[0];
    if (!doc) {
        return NextResponse.json({ error: "Not found" }, { status: 404 });
    }

    // Linked entries with full detail (category/subcategory/vendor/unit), report period (for the
    // deep link), and live amount. Joins mirror GET /api/entries.
    const entryRows = await db
        .select({
            entryId: entries.id,
            period: accountabilityReports.period,
            date: entries.date,
            description: entries.description,
            amount: entries.amount,
            category: categories.name,
            subcategory: subcategories.name,
            vendor: vendors.name,
            unitCode: units.code,
            sourceAttachmentId: documentEntries.sourceAttachmentId,
        })
        .from(documentEntries)
        .innerJoin(entries, eq(documentEntries.entryId, entries.id))
        .innerJoin(accountabilityReports, eq(entries.reportId, accountabilityReports.id))
        .innerJoin(subcategories, eq(entries.subcategoryId, subcategories.id))
        .innerJoin(categories, eq(subcategories.categoryId, categories.id))
        .leftJoin(vendors, eq(entries.vendorId, vendors.id))
        .leftJoin(units, eq(entries.unitId, units.id))
        .where(eq(documentEntries.documentId, id))
        .orderBy(accountabilityReports.period, entries.date);

    const sumEntries = entryRows.reduce((acc, e) => acc + e.amount, 0);

    // Image sources: the document's page image(s) live in its provenance attachments. Resolve each
    // distinct source attachment to its analysis id (the key the existing page-image routes use);
    // inner-join to attachment_analyses so attachments without an analysis simply contribute nothing.
    const sourceRows = await db
        .select({
            attachmentId: documentEntries.sourceAttachmentId,
            analysisId: attachmentAnalyses.id,
            entryId: documentEntries.entryId,
            period: accountabilityReports.period,
        })
        .from(documentEntries)
        .innerJoin(attachmentAnalyses, eq(attachmentAnalyses.attachmentId, documentEntries.sourceAttachmentId))
        .innerJoin(entries, eq(documentEntries.entryId, entries.id))
        .innerJoin(accountabilityReports, eq(entries.reportId, accountabilityReports.id))
        .where(eq(documentEntries.documentId, id));

    const seenAnalysis = new Set<string>();
    const imageSources = sourceRows.filter(s => {
        if (seenAnalysis.has(s.analysisId)) return false;
        seenAnalysis.add(s.analysisId);
        return true;
    });

    // Related documents: other real documents linked to any of this document's entries (self excluded).
    // Their sumEntries/status are computed over each related document's OWN full link set, so the badge
    // matches what that document's own detail page shows.
    const entryIds = entryRows.map(e => e.entryId);
    let relatedDocuments: Array<{
        id: string;
        documentNumber: string;
        issuerCnpj: string;
        issuerName: string | null;
        documentType: string | null;
        totalValue: number | null;
        sumEntries: number;
        status: ReturnType<typeof documentStatus>;
    }> = [];

    if (entryIds.length > 0) {
        const relatedIdRows = await db
            .selectDistinct({ documentId: documentEntries.documentId })
            .from(documentEntries)
            .where(and(inArray(documentEntries.entryId, entryIds), ne(documentEntries.documentId, id)));
        const relatedIds = relatedIdRows.map(r => r.documentId);

        if (relatedIds.length > 0) {
            const relatedRows = await db
                .select({
                    id: documents.id,
                    documentNumber: documents.documentNumber,
                    issuerCnpj: documents.issuerCnpj,
                    issuerName: documents.issuerName,
                    documentType: documents.documentType,
                    totalValue: documents.totalValue,
                    sumEntries: sql<number>`coalesce(sum(${entries.amount}), 0)`.as("sum_entries"),
                })
                .from(documents)
                .leftJoin(documentEntries, eq(documentEntries.documentId, documents.id))
                .leftJoin(entries, eq(documentEntries.entryId, entries.id))
                .where(inArray(documents.id, relatedIds))
                .groupBy(documents.id)
                .orderBy(documents.issuerName, documents.documentNumber);

            relatedDocuments = relatedRows.map(r => ({
                ...r,
                status: documentStatus(r.sumEntries, r.totalValue),
            }));
        }
    }

    return NextResponse.json({
        id: doc.id,
        documentNumber: doc.documentNumber,
        issuerCnpj: doc.issuerCnpj,
        issuerName: doc.issuerName,
        documentType: doc.documentType,
        totalValue: doc.totalValue,
        sumEntries,
        status: documentStatus(sumEntries, doc.totalValue),
        entries: entryRows,
        imageSources,
        relatedDocuments,
    });
}
