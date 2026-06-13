import { initAuth } from "@/auth";
import { getDb } from "@/db";
import { alerts } from "@/db/fiscal.schema";
import { isAuthorized, UNAUTHORIZED_STATUS } from "@/lib/auth-access";
import { shapeAlertRow } from "./shape";
import { asc, desc } from "drizzle-orm";
import { headers } from "next/headers";
import { NextResponse } from "next/server";

export async function GET() {
    const authInstance = await initAuth();
    const session = await authInstance.api.getSession({ headers: await headers() });
    if (!isAuthorized(session)) {
        return NextResponse.json({ error: "Unauthorized" }, { status: UNAUTHORIZED_STATUS });
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
            metadata: alerts.metadata,
        })
        .from(alerts)
        .orderBy(asc(alerts.resolved), desc(alerts.severity), desc(alerts.referencePeriod));

    return NextResponse.json(rows.map(shapeAlertRow));
}
