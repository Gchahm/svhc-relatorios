import { initAuth } from "@/auth";
import { getDb } from "@/db";
import { documentAnalyses, documents, entries, subcategories, categories, vendors } from "@/db/fiscal.schema";
import { eq, desc } from "drizzle-orm";
import { headers } from "next/headers";
import { NextResponse } from "next/server";

const ALLOWED_ROLES = ["admin", "member"];

export async function GET() {
    const authInstance = await initAuth();
    const session = await authInstance.api.getSession({ headers: await headers() });
    const userRole = (session?.user as { role?: string } | undefined)?.role;
    if (!session || !userRole || !ALLOWED_ROLES.includes(userRole)) {
        return NextResponse.json({ error: "Unauthorized" }, { status: 403 });
    }

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
        .leftJoin(subcategories, eq(entries.subcategoryId, subcategories.id))
        .leftJoin(categories, eq(subcategories.categoryId, categories.id))
        .leftJoin(vendors, eq(entries.vendorId, vendors.id))
        .orderBy(desc(documentAnalyses.analyzedAt));

    return NextResponse.json(rows);
}
