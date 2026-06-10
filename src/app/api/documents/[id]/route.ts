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
    attachments,
    attachmentAnalyses,
    attachmentAnalysisRecords,
} from "@/db/fiscal.schema";
import { documentStatus } from "@/lib/documents";
import { parsePage } from "@/lib/r2";
import { and, eq, inArray, ne, sql } from "drizzle-orm";
import { headers } from "next/headers";
import { NextResponse } from "next/server";

const ALLOWED_ROLES = ["admin", "member"];

// Artifact roles that ARE the fiscal document itself (as opposed to payment artifacts like a
// boleto or payment proof that travel in the same attachment bundle).
const DOCUMENT_ROLES = new Set(["invoice", "nfse"]);

const digitsOnly = (s: string | null | undefined) => (s ?? "").replace(/\D/g, "");
const alnumUpper = (s: string | null | undefined) => (s ?? "").replace(/[^0-9a-z]/gi, "").toUpperCase();

/**
 * Score how strongly one extracted page matches the target document. A bundle holds several pages
 * (invoice + boleto + payment proof); the page whose issuer CNPJ / document number / fiscal role
 * line up with the document is the document's own page. Higher = better match.
 */
function pageMatchScore(
    page: { artifactRole: string | null; cnpj: string | null; number: string | null },
    docCnpj: string,
    docNumber: string
): number {
    let score = 0;
    if (docCnpj && digitsOnly(page.cnpj) === docCnpj) score += 2;
    if (docNumber && alnumUpper(page.number) === alnumUpper(docNumber)) score += 2;
    if (page.artifactRole && DOCUMENT_ROLES.has(page.artifactRole)) score += 1;
    return score;
}

const ROLE_LABELS: Record<string, string> = {
    invoice: "Invoice",
    nfse: "NFS-e",
    boleto: "Boleto",
    payment_proof: "Payment proof",
    other: "Other",
};

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
            filePath: attachments.filePath,
            entryId: documentEntries.entryId,
            period: accountabilityReports.period,
        })
        .from(documentEntries)
        .innerJoin(attachmentAnalyses, eq(attachmentAnalyses.attachmentId, documentEntries.sourceAttachmentId))
        .innerJoin(attachments, eq(attachments.id, documentEntries.sourceAttachmentId))
        .innerJoin(entries, eq(documentEntries.entryId, entries.id))
        .innerJoin(accountabilityReports, eq(entries.reportId, accountabilityReports.id))
        .where(eq(documentEntries.documentId, id));

    const seenAnalysis = new Set<string>();
    const distinctSources = sourceRows.filter(s => {
        if (seenAnalysis.has(s.analysisId)) return false;
        seenAnalysis.add(s.analysisId);
        return true;
    });

    // Per-page extraction records for those analyses — they carry the artifact role and the page's
    // own extracted issuer CNPJ / document number, which is how we tell which page IS the document
    // (vs. its boleto / payment proof) and label every page.
    const analysisIds = distinctSources.map(s => s.analysisId);
    const recordRows = analysisIds.length
        ? await db
              .select({
                  analysisId: attachmentAnalysisRecords.attachmentAnalysisId,
                  pageLabel: attachmentAnalysisRecords.pageLabel,
                  artifactRole: attachmentAnalysisRecords.artifactRole,
                  response: attachmentAnalysisRecords.response,
              })
              .from(attachmentAnalysisRecords)
              .where(inArray(attachmentAnalysisRecords.attachmentAnalysisId, analysisIds))
        : [];

    // Index records by (analysisId, pageLabel) with their parsed CNPJ / number.
    const recordByPage = new Map<string, { artifactRole: string | null; cnpj: string | null; number: string | null }>();
    for (const r of recordRows) {
        let cnpj: string | null = null;
        let number: string | null = null;
        if (r.response) {
            try {
                const v = JSON.parse(r.response) as Record<string, unknown>;
                cnpj = typeof v.cnpj_emitente === "string" ? v.cnpj_emitente : null;
                number = typeof v.numero_documento === "string" ? v.numero_documento : null;
            } catch {
                // unparseable page response — leave as nulls (still labeled by role below)
            }
        }
        if (r.pageLabel)
            recordByPage.set(`${r.analysisId}|${r.pageLabel}`, { artifactRole: r.artifactRole, cnpj, number });
    }

    const docCnpj = digitsOnly(doc.issuerCnpj);
    const docNumber = doc.documentNumber;

    const imageSources = distinctSources.map(s => {
        // Parse the attachment's page list (label/index/ext) exactly as the /pages route does.
        const pageSegments = (s.filePath ?? "")
            .split(";")
            .map(seg => seg.trim())
            .filter(Boolean)
            .map(seg => parsePage(seg))
            .filter((p): p is { pageLabel: string; pageIndex: number; ext: string } => p.pageLabel !== null)
            .sort((a, b) => a.pageIndex - b.pageIndex);

        let bestLabel: string | null = null;
        let bestScore = 0;
        const pages = pageSegments.map(p => {
            const rec = recordByPage.get(`${s.analysisId}|${p.pageLabel}`) ?? null;
            const score = rec ? pageMatchScore(rec, docCnpj, docNumber) : 0;
            if (score > bestScore) {
                bestScore = score;
                bestLabel = p.pageLabel;
            }
            return {
                pageLabel: p.pageLabel,
                pageIndex: p.pageIndex,
                imageUrl: `/api/attachment-analyses/${s.analysisId}/image/${p.pageLabel}`,
                artifactRole: rec?.artifactRole ?? null,
                roleLabel: rec?.artifactRole ? (ROLE_LABELS[rec.artifactRole] ?? rec.artifactRole) : null,
            };
        });

        // Fallback so there is always a representative page when nothing scored (the document was
        // built from this analysis, so a page should match — but stay safe): the first page.
        const documentPageLabel = bestLabel ?? (pages.length > 0 ? pages[0].pageLabel : null);

        return {
            attachmentId: s.attachmentId,
            analysisId: s.analysisId,
            entryId: s.entryId,
            period: s.period,
            documentPageLabel,
            pages: pages.map(p => ({ ...p, isDocument: p.pageLabel === documentPageLabel })),
        };
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
