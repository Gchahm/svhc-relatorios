import { initAuth } from "@/auth";
import { getDb } from "@/db";
import { documentAnalyses, documents } from "@/db/fiscal.schema";
import { contentTypeForExt, getDocumentsBucket, objectKeyFromFilePath, parsePage } from "@/lib/r2";
import { eq } from "drizzle-orm";
import { headers } from "next/headers";
import { type NextRequest, NextResponse } from "next/server";

const ALLOWED_ROLES = ["admin", "member"];

/**
 * GET /api/document-analyses/[id]/image/[page]
 *
 * Streams one page image from the R2 `DOCUMENTS` bucket. The object key is resolved server-side
 * from the document's `file_path`, so the client never supplies a raw key — `[page]` can only
 * select among this document's own pages (Constitution IV).
 */
export async function GET(_request: NextRequest, { params }: { params: Promise<{ id: string; page: string }> }) {
    const authInstance = await initAuth();
    const session = await authInstance.api.getSession({ headers: await headers() });
    const userRole = (session?.user as { role?: string } | undefined)?.role;
    if (!session || !userRole || !ALLOWED_ROLES.includes(userRole)) {
        return NextResponse.json({ error: "Unauthorized" }, { status: 403 });
    }

    const { id, page } = await params;
    const db = await getDb();

    const rows = await db
        .select({ filePath: documents.filePath })
        .from(documentAnalyses)
        .innerJoin(documents, eq(documentAnalyses.documentId, documents.id))
        .where(eq(documentAnalyses.id, id))
        .limit(1);

    const filePath = rows[0]?.filePath;
    if (!filePath) {
        return NextResponse.json({ error: "Not found" }, { status: 404 });
    }

    // Find the file_path segment whose page label matches the requested page.
    const segment = filePath
        .split(";")
        .map(s => s.trim())
        .filter(Boolean)
        .find(s => parsePage(s).pageLabel === page);

    if (!segment) {
        return NextResponse.json({ error: "Not found" }, { status: 404 });
    }

    const key = objectKeyFromFilePath(segment);
    const bucket = await getDocumentsBucket();
    const object = await bucket.get(key);
    if (!object) {
        return NextResponse.json({ error: "Not found" }, { status: 404 });
    }

    const { ext } = parsePage(segment);
    // R2's body is a @cloudflare/workers-types ReadableStream, which the DOM `Response` typing
    // doesn't recognize as BodyInit; the Workers runtime accepts it at runtime. Cast to bridge.
    const body = object.body as unknown as BodyInit;
    return new Response(body, {
        headers: {
            "Content-Type": contentTypeForExt(ext),
            "Cache-Control": "private, max-age=3600",
        },
    });
}
