import { getDb } from "@/db";
import { entries, subcategories, categories, accountabilityReports, vendors, units } from "@/db/fiscal.schema";
import { eq } from "drizzle-orm";
import { NextResponse } from "next/server";

export async function GET() {
    const db = await getDb();

    const rows = await db
        .select({
            id: entries.id,
            date: entries.date,
            description: entries.description,
            amount: entries.amount,
            movementType: entries.movementType,
            sourceUrl: entries.sourceUrl,
            period: accountabilityReports.period,
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
        .orderBy(accountabilityReports.period, entries.date);

    return NextResponse.json(rows);
}
