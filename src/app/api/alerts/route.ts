import { initAuth } from "@/auth";
import { getDb } from "@/db";
import { alerts } from "@/db/fiscal.schema";
import { asc, desc } from "drizzle-orm";
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
            id: alerts.id,
            type: alerts.type,
            severity: alerts.severity,
            title: alerts.title,
            description: alerts.description,
            referencePeriod: alerts.referencePeriod,
            resolved: alerts.resolved,
            resolvedAt: alerts.resolvedAt,
            notes: alerts.notes,
        })
        .from(alerts)
        .orderBy(asc(alerts.resolved), desc(alerts.severity), desc(alerts.referencePeriod));

    return NextResponse.json(rows);
}
