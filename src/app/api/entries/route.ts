import { initAuth } from "@/auth";
import { getDb } from "@/db";
import { entries, subcategories, categories, accountabilityReports, vendors, units } from "@/db/fiscal.schema";
import { eq } from "drizzle-orm";
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

    const period = request.nextUrl.searchParams.get("period");
    if (!period) {
        return NextResponse.json({ error: "period query parameter is required" }, { status: 400 });
    }

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
        .where(eq(accountabilityReports.period, period))
        .orderBy(entries.date);

    return NextResponse.json(rows);
}
