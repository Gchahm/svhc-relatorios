import { initAuth } from "@/auth";
import { getDb } from "@/db";
import {
    documentAnalyses,
    documents,
    entries,
    subcategories,
    categories,
    vendors,
    accountabilityReports,
} from "@/db/fiscal.schema";
import { eq, desc, sql } from "drizzle-orm";
import { headers } from "next/headers";
import { type NextRequest, NextResponse } from "next/server";

const ALLOWED_ROLES = ["admin", "member"];

export async function GET(request: NextRequest) {
    const authInstance = await initAuth();
    const session = await authInstance.api.getSession({ headers: await headers() });
    const userRole = (session?.user as { role?: string } | undefined)?.role;
    if (!session || !userRole || !ALLOWED_ROLES.includes(userRole)) {
        return NextResponse.json({ error: "Unauthorized" }, { status: 403 });
    }

    // Optional period scoping: when present, restrict to analyses whose entry belongs to the period.
    const period = request.nextUrl.searchParams.get("period");

    const db = await getDb();

    const rows = await db
        .select({
            id: documentAnalyses.id,
            documentId: documentAnalyses.documentId,
            analyzedAt: documentAnalyses.analyzedAt,
            documentType: documentAnalyses.documentType,
            extractedAmount: documentAnalyses.extractedAmount,
            amountMatch: documentAnalyses.amountMatch,
            extractedCnpj: documentAnalyses.extractedCnpj,
            issuerName: documentAnalyses.issuerName,
            vendorMatch: documentAnalyses.vendorMatch,
            extractedDate: documentAnalyses.extractedDate,
            dateMatch: documentAnalyses.dateMatch,
            documentNumber: documentAnalyses.documentNumber,
            serviceDescription: documentAnalyses.serviceDescription,
            error: documentAnalyses.error,
            // Entry data
            entryId: sql<string>`${entries.id}`.as("entry_id"),
            entryDate: entries.date,
            entryDescription: entries.description,
            entryAmount: entries.amount,
            entryMovementType: entries.movementType,
            // Related
            vendorName: vendors.name,
            subcategoryName: subcategories.name,
            categoryName: categories.name,
        })
        .from(documentAnalyses)
        .innerJoin(documents, eq(documentAnalyses.documentId, documents.id))
        .innerJoin(entries, eq(documents.entryId, entries.id))
        .innerJoin(accountabilityReports, eq(entries.reportId, accountabilityReports.id))
        .leftJoin(subcategories, eq(entries.subcategoryId, subcategories.id))
        .leftJoin(categories, eq(subcategories.categoryId, categories.id))
        .leftJoin(vendors, eq(entries.vendorId, vendors.id))
        .where(period ? eq(accountabilityReports.period, period) : undefined)
        .orderBy(desc(documentAnalyses.analyzedAt));

    return NextResponse.json(rows);
}
