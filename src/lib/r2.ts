import { getCloudflareContext } from "@opennextjs/cloudflare";

/**
 * Returns the R2 bucket holding fiscal-document page images.
 *
 * Mirrors `getDb()` in `src/db/index.ts`: resolves the Cloudflare binding from the runtime
 * context. The `DOCUMENTS` binding is declared in `wrangler.toml` and typed in `env.d.ts`.
 */
export async function getDocumentsBucket() {
    const { env } = await getCloudflareContext({ async: true });
    return env.DOCUMENTS;
}

/**
 * Normalize one `documents.file_path` segment into its R2 object key.
 *
 * The canonical mapping (single source of truth) is documented in
 * `specs/012-r2-document-images/data-model.md`. The upload script
 * (`scripts/upload-images-to-r2.mjs`) MUST replicate this exactly so writes and reads agree.
 *
 * Example: `../data/scrape/2025-12/<id>_p2.png` -> `2025-12/<id>_p2.png`
 */
export function objectKeyFromFilePath(segment: string): string {
    const normalized = segment.trim().replace(/^(\.\.\/)+/, "");
    const marker = "data/scrape/";
    const idx = normalized.lastIndexOf(marker);
    return idx === -1 ? normalized : normalized.slice(idx + marker.length);
}

export interface ParsedPage {
    /** Page label, e.g. `p2` (parsed from the `_p<N>` basename suffix), or null if absent. */
    pageLabel: string | null;
    /** 0-based page index (N - 1), aligning with `document_analysis_records.page_index`. */
    pageIndex: number | null;
    /** Lowercased file extension, e.g. `png`. */
    ext: string;
}

/**
 * Parse the page label, 0-based index, and extension from a `file_path` segment's basename.
 *
 * Example: `.../<id>_p3.jpg` -> `{ pageLabel: "p3", pageIndex: 2, ext: "jpg" }`
 */
export function parsePage(segment: string): ParsedPage {
    const basename = objectKeyFromFilePath(segment).split("/").pop() ?? "";
    const match = basename.match(/_p(\d+)\.[^.]+$/);
    const ext = (basename.split(".").pop() ?? "").toLowerCase();
    if (!match) {
        return { pageLabel: null, pageIndex: null, ext };
    }
    const n = Number(match[1]);
    return { pageLabel: `p${n}`, pageIndex: n - 1, ext };
}

/** Map a file extension to the image content type the route serves. */
export function contentTypeForExt(ext: string): string {
    switch (ext.toLowerCase()) {
        case "jpg":
        case "jpeg":
            return "image/jpeg";
        case "png":
            return "image/png";
        default:
            return "application/octet-stream";
    }
}
