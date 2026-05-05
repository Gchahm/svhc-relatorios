import { initAuth } from "@/auth";
import { getDb } from "@/db";
import { entries, subcategories, accountabilityReports, units } from "@/db/fiscal.schema";
import { eq } from "drizzle-orm";
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
            id: entries.id,
            period: accountabilityReports.period,
            date: entries.date,
            unitCode: units.code,
            description: entries.description,
            amount: entries.amount,
        })
        .from(entries)
        .innerJoin(accountabilityReports, eq(entries.reportId, accountabilityReports.id))
        .innerJoin(subcategories, eq(entries.subcategoryId, subcategories.id))
        .leftJoin(units, eq(entries.unitId, units.id))
        .where(eq(subcategories.name, "EXTRAS - MULTA"))
        .orderBy(entries.date);

    return NextResponse.json(rows);
}
