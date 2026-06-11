import { initAuth } from "@/auth";
import { getDb } from "@/db";
import { alerts } from "@/db/fiscal.schema";
import { eq } from "drizzle-orm";
import { headers } from "next/headers";
import { type NextRequest, NextResponse } from "next/server";

const ALLOWED_ROLES = ["admin", "member"];

// Full alert projection shared by GET and PATCH so both return a complete object.
const alertColumns = {
    id: alerts.id,
    type: alerts.type,
    severity: alerts.severity,
    title: alerts.title,
    description: alerts.description,
    referencePeriod: alerts.referencePeriod,
    createdAt: alerts.createdAt,
    resolved: alerts.resolved,
    resolvedAt: alerts.resolvedAt,
    notes: alerts.notes,
    metadata: alerts.metadata,
};

export async function GET(_request: NextRequest, { params }: { params: Promise<{ id: string }> }) {
    const authInstance = await initAuth();
    const session = await authInstance.api.getSession({ headers: await headers() });
    const userRole = (session?.user as { role?: string } | undefined)?.role;
    if (!session || !userRole || !ALLOWED_ROLES.includes(userRole)) {
        return NextResponse.json({ error: "Unauthorized" }, { status: 403 });
    }

    const { id } = await params;
    const db = await getDb();

    const row = (await db.select(alertColumns).from(alerts).where(eq(alerts.id, id)).limit(1))[0];
    if (!row) {
        return NextResponse.json({ error: "Alert not found" }, { status: 404 });
    }
    return NextResponse.json(row);
}

export async function PATCH(request: NextRequest, { params }: { params: Promise<{ id: string }> }) {
    const authInstance = await initAuth();
    const session = await authInstance.api.getSession({ headers: await headers() });
    const userRole = (session?.user as { role?: string } | undefined)?.role;
    if (!session || !userRole || !ALLOWED_ROLES.includes(userRole)) {
        return NextResponse.json({ error: "Unauthorized" }, { status: 403 });
    }

    const { id } = await params;
    const body = await request.json();
    const { resolved, notes } = body as { resolved: boolean; notes?: string };

    const db = await getDb();

    await db
        .update(alerts)
        .set({
            resolved,
            resolvedAt: resolved ? new Date() : null,
            notes: notes ?? null,
        })
        .where(eq(alerts.id, id));

    const updated = await db.select(alertColumns).from(alerts).where(eq(alerts.id, id)).limit(1);

    if (updated.length === 0) {
        return NextResponse.json({ error: "Alert not found" }, { status: 404 });
    }

    return NextResponse.json(updated[0]);
}
