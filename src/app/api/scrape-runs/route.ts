import { initAuth } from "@/auth";
import { getDb } from "@/db";
import { scrapeRuns, accountabilityReports } from "@/db/fiscal.schema";
import { desc, asc } from "drizzle-orm";
import { headers } from "next/headers";
import { NextResponse } from "next/server";

const ALLOWED_ROLES = ["admin", "member"];

function findMissingPeriods(periods: string[]): string[] {
    if (periods.length < 2) return [];

    const sorted = [...periods].sort();
    const missing: string[] = [];

    for (let i = 0; i < sorted.length - 1; i++) {
        const [year, month] = sorted[i].split("-").map(Number);
        const [nextYear, nextMonth] = sorted[i + 1].split("-").map(Number);

        let curYear = year;
        let curMonth = month + 1;

        while (curYear < nextYear || (curYear === nextYear && curMonth < nextMonth)) {
            const paddedMonth = String(curMonth).padStart(2, "0");
            missing.push(`${curYear}-${paddedMonth}`);

            curMonth++;
            if (curMonth > 12) {
                curMonth = 1;
                curYear++;
            }
        }
    }

    return missing;
}

export async function GET() {
    const authInstance = await initAuth();
    const session = await authInstance.api.getSession({ headers: await headers() });
    const userRole = (session?.user as { role?: string } | undefined)?.role;
    if (!session || !userRole || !ALLOWED_ROLES.includes(userRole)) {
        return NextResponse.json({ error: "Unauthorized" }, { status: 403 });
    }

    const db = await getDb();

    const [runs, reports] = await Promise.all([
        db
            .select({
                id: scrapeRuns.id,
                executedAt: scrapeRuns.executedAt,
                status: scrapeRuns.status,
                errors: scrapeRuns.errors,
                durationSeconds: scrapeRuns.durationSeconds,
            })
            .from(scrapeRuns)
            .orderBy(desc(scrapeRuns.executedAt)),
        db
            .select({ period: accountabilityReports.period })
            .from(accountabilityReports)
            .orderBy(asc(accountabilityReports.period)),
    ]);

    const periods = [...new Set(reports.map(r => r.period))];
    const missingPeriods = findMissingPeriods(periods);

    return NextResponse.json({ runs, missingPeriods });
}
