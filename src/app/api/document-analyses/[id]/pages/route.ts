import { initAuth } from "@/auth";
import { getDb } from "@/db";
import { documentAnalyses, documents } from "@/db/fiscal.schema";
import { parsePage } from "@/lib/r2";
import { eq } from "drizzle-orm";
import { headers } from "next/headers";
import { type NextRequest, NextResponse } from "next/server";

const ALLOWED_ROLES = ["admin", "member"];

/**
 * GET /api/document-analyses/[id]/pages
 *
 * Returns the ordered list of page images for one document analysis, derived from
 * `documents.file_path`. No R2 access — the image route resolves and streams the bytes.
 */
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
        .select({ filePath: documents.filePath })
        .from(documentAnalyses)
        .innerJoin(documents, eq(documentAnalyses.documentId, documents.id))
        .where(eq(documentAnalyses.id, id))
        .limit(1);

    if (rows.length === 0) {
        return NextResponse.json({ error: "Not found" }, { status: 404 });
    }

    const filePath = rows[0].filePath;
    if (!filePath) {
        return NextResponse.json([]);
    }

    const pages = filePath
        .split(";")
        .map(segment => segment.trim())
        .filter(Boolean)
        .map(segment => {
            const { pageLabel, pageIndex, ext } = parsePage(segment);
            return { pageIndex, pageLabel, ext };
        })
        // Only pages we can address by label (the image route keys off pageLabel).
        .filter((p): p is { pageIndex: number; pageLabel: string; ext: string } => p.pageLabel !== null)
        .sort((a, b) => a.pageIndex - b.pageIndex)
        .map(p => ({
            ...p,
            imageUrl: `/api/document-analyses/${id}/image/${p.pageLabel}`,
        }));

    return NextResponse.json(pages);
}
