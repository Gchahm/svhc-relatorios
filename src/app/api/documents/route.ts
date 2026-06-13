import { initAuth } from "@/auth";
import { getDb } from "@/db";
import { documents, documentEntries, entries } from "@/db/fiscal.schema";
import { isAuthorized, UNAUTHORIZED_STATUS } from "@/lib/auth-access";
import { shapeDocumentRow } from "./shape";
import { eq, sql } from "drizzle-orm";
import { headers } from "next/headers";
import { NextResponse } from "next/server";

export async function GET() {
    const authInstance = await initAuth();
    const session = await authInstance.api.getSession({ headers: await headers() });
    if (!isAuthorized(session)) {
        return NextResponse.json({ error: "Unauthorized" }, { status: UNAUTHORIZED_STATUS });
    }

    const db = await getDb();

    // One row per document with its link aggregates (live entry amounts). LEFT JOINs so a
    // document with no links still appears (linkedCount 0). Status derived below.
    const rows = await db
        .select({
            id: documents.id,
            documentNumber: documents.documentNumber,
            issuerCnpj: documents.issuerCnpj,
            issuerName: documents.issuerName,
            documentType: documents.documentType,
            totalValue: documents.totalValue,
            linkedCount: sql<number>`count(${documentEntries.id})`.as("linked_count"),
            sumEntries: sql<number>`coalesce(sum(${entries.amount}), 0)`.as("sum_entries"),
        })
        .from(documents)
        .leftJoin(documentEntries, eq(documentEntries.documentId, documents.id))
        .leftJoin(entries, eq(documentEntries.entryId, entries.id))
        .groupBy(documents.id)
        .orderBy(documents.issuerName, documents.documentNumber);

    return NextResponse.json(rows.map(shapeDocumentRow));
}
