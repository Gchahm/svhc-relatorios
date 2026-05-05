import { initAuth } from "@/auth";
import { getDb } from "@/db";
import { entries, subcategories, categories, accountabilityReports } from "@/db/fiscal.schema";
import { eq, sql } from "drizzle-orm";
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
            period: accountabilityReports.period,
            category: categories.name,
            subcategory: subcategories.name,
            movementType: entries.movementType,
            total: sql<number>`sum(${entries.amount})`.as("total"),
            count: sql<number>`count(*)`.as("count"),
        })
        .from(entries)
        .innerJoin(accountabilityReports, eq(entries.reportId, accountabilityReports.id))
        .innerJoin(subcategories, eq(entries.subcategoryId, subcategories.id))
        .innerJoin(categories, eq(subcategories.categoryId, categories.id))
        .groupBy(accountabilityReports.period, categories.name, subcategories.name, entries.movementType)
        .orderBy(accountabilityReports.period, categories.name, subcategories.name);

    return NextResponse.json(rows);
}
