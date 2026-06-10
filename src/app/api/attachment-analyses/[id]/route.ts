import { initAuth } from "@/auth";
import { getDb } from "@/db";
import { attachmentAnalysisRecords } from "@/db/fiscal.schema";
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
            id: attachmentAnalysisRecords.id,
            analysisType: attachmentAnalysisRecords.analysisType,
            pageIndex: attachmentAnalysisRecords.pageIndex,
            pageLabel: attachmentAnalysisRecords.pageLabel,
            artifactRole: attachmentAnalysisRecords.artifactRole,
            response: attachmentAnalysisRecords.response,
            rawText: attachmentAnalysisRecords.rawText,
            parseError: attachmentAnalysisRecords.parseError,
        })
        .from(attachmentAnalysisRecords)
        .where(eq(attachmentAnalysisRecords.attachmentAnalysisId, id))
        // Stable page order; null pageIndex sorts last.
        .orderBy(sql`${attachmentAnalysisRecords.pageIndex} is null`, asc(attachmentAnalysisRecords.pageIndex));

    return NextResponse.json(rows);
}
