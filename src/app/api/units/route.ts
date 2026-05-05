import { initAuth } from "@/auth";
import { getDb } from "@/db";
import { entries, units, accountabilityReports } from "@/db/fiscal.schema";
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
            unitId: units.id,
            code: units.code,
            block: units.block,
            number: units.number,
            period: accountabilityReports.period,
            total: sql<number>`sum(${entries.amount})`.as("total"),
            entryCount: sql<number>`count(*)`.as("entry_count"),
        })
        .from(entries)
        .innerJoin(units, eq(entries.unitId, units.id))
        .innerJoin(accountabilityReports, eq(entries.reportId, accountabilityReports.id))
        .groupBy(units.id, units.code, units.block, units.number, accountabilityReports.period)
        .orderBy(units.code, accountabilityReports.period);

    return NextResponse.json(rows);
}
