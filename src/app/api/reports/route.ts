import { initAuth } from "@/auth";
import { getDb } from "@/db";
import { accountabilityReports } from "@/db/fiscal.schema";
import { desc } from "drizzle-orm";
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
            id: accountabilityReports.id,
            period: accountabilityReports.period,
            totalRevenue: accountabilityReports.totalRevenue,
            totalExpenses: accountabilityReports.totalExpenses,
            openingBalance: accountabilityReports.openingBalance,
            monthBalance: accountabilityReports.monthBalance,
            accumulatedBalance: accountabilityReports.accumulatedBalance,
            sourceUrl: accountabilityReports.sourceUrl,
        })
        .from(accountabilityReports)
        .orderBy(desc(accountabilityReports.period));

    return NextResponse.json(rows);
}
