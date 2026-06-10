import { initAuth } from "@/auth";
import { getDb } from "@/db";
import { documents, documentEntries, entries, accountabilityReports } from "@/db/fiscal.schema";
import { documentStatus } from "@/lib/documents";
import { eq } from "drizzle-orm";
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

    // Linked entries with their report period (for the deep link) and live amount.
    const entryRows = await db
        .select({
            entryId: entries.id,
            period: accountabilityReports.period,
            date: entries.date,
            description: entries.description,
            amount: entries.amount,
            sourceAttachmentId: documentEntries.sourceAttachmentId,
        })
        .from(documentEntries)
        .innerJoin(entries, eq(documentEntries.entryId, entries.id))
        .innerJoin(accountabilityReports, eq(entries.reportId, accountabilityReports.id))
        .where(eq(documentEntries.documentId, id))
        .orderBy(accountabilityReports.period, entries.date);

    const sumEntries = entryRows.reduce((acc, e) => acc + e.amount, 0);

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
    });
}
