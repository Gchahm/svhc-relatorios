import { initAuth } from "@/auth";
import { getDb } from "@/db";
import { documentAnalysisRecords } from "@/db/fiscal.schema";
import { asc, eq, sql } from "drizzle-orm";
import { headers } from "next/headers";
import { type NextRequest, NextResponse } from "next/server";

const ALLOWED_ROLES = ["admin", "member"];

export async function GET(_request: NextRequest, { params }: { params: Promise<{ id: string }> }) {
    const authInstance = await initAuth();
    const session = await authInstance.api.getSession({ headers: await headers() });
    const userRole = (session?.user as { role?: string } | undefined)?.role;
    if (!session || !userRole || !ALLOWED_ROLES.includes(userRole)) {
        return NextResponse.json({ error: "Unauthorized" }, { status: 403 });
    }

    const { id } = await params;
    const db = await getDb();

    const rows = await db
        .select({
            id: documentAnalysisRecords.id,
            analysisType: documentAnalysisRecords.analysisType,
            pageIndex: documentAnalysisRecords.pageIndex,
            pageLabel: documentAnalysisRecords.pageLabel,
            artifactRole: documentAnalysisRecords.artifactRole,
            response: documentAnalysisRecords.response,
            rawText: documentAnalysisRecords.rawText,
            parseError: documentAnalysisRecords.parseError,
        })
        .from(documentAnalysisRecords)
        .where(eq(documentAnalysisRecords.documentAnalysisId, id))
        // Stable page order; null pageIndex sorts last.
        .orderBy(sql`${documentAnalysisRecords.pageIndex} is null`, asc(documentAnalysisRecords.pageIndex));

    return NextResponse.json(rows);
}
