#!/usr/bin/env node
/**
 * Upload fiscal-document page images into the R2 `fiscal-documents` bucket.
 *
 * Walks the scraped period folders (`data/scrape/<period>/`) for page-image files and uploads
 * each via `wrangler r2 object put`. R2 `put` is an upsert, so re-running is idempotent — the
 * same key is overwritten, never duplicated.
 *
 * The object key is `<period>/<basename>` — the path relative to `data/scrape/`. This MUST match
 * `objectKeyFromFilePath()` in `src/lib/r2.ts`; the canonical mapping lives in
 * `specs/012-r2-document-images/data-model.md`.
 *
 * Usage:
 *   node scripts/upload-images-to-r2.mjs [--input data/scrape] [--period 2025-12] [--remote] [--dry-run]
 */

import { execSync } from "node:child_process";
import { readdirSync, statSync, existsSync } from "node:fs";
import { parseArgs } from "node:util";
import { join, basename } from "node:path";

const { values: args } = parseArgs({
    options: {
        input: { type: "string", short: "i", default: "data/scrape" },
        period: { type: "string", short: "p" },
        remote: { type: "boolean", default: false },
        "dry-run": { type: "boolean", default: false },
    },
});

const inputPath = args.input;
const isRemote = args.remote;
const isDryRun = args["dry-run"];
const BUCKET = "fiscal-documents";
const IMAGE_RE = /_p\d+\.(jpg|jpeg|png)$/i;

function contentTypeForFile(name) {
    const ext = (name.split(".").pop() ?? "").toLowerCase();
    if (ext === "jpg" || ext === "jpeg") return "image/jpeg";
    if (ext === "png") return "image/png";
    return "application/octet-stream";
}

/** Period subdirectories under the input path (e.g. `2025-12`), or just the one passed via --period. */
function resolvePeriodDirs() {
    if (args.period) {
        const dir = join(inputPath, args.period);
        if (!existsSync(dir) || !statSync(dir).isDirectory()) {
            throw new Error(`Period directory not found: ${dir}`);
        }
        return [args.period];
    }
    if (!existsSync(inputPath)) throw new Error(`Input path not found: ${inputPath}`);
    return readdirSync(inputPath)
        .filter(name => {
            const full = join(inputPath, name);
            return statSync(full).isDirectory();
        })
        .sort();
}

/** Collect { key, path } for every page image under a period directory. */
function collectImages(period) {
    const dir = join(inputPath, period);
    return readdirSync(dir)
        .filter(name => IMAGE_RE.test(name))
        .sort()
        .map(name => ({ key: `${period}/${name}`, path: join(dir, name), name }));
}

// Main
const periods = resolvePeriodDirs();
const target = isRemote ? "--remote" : "--local";

let total = 0;
let uploaded = 0;
let failed = 0;

console.log(`Uploading page images to R2 bucket "${BUCKET}" (${isRemote ? "remote" : "local"})`);
console.log(`Periods: ${periods.join(", ") || "(none)"}\n`);

for (const period of periods) {
    const images = collectImages(period);
    if (images.length === 0) {
        console.log(`  ${period}: 0 images (skipped)`);
        continue;
    }
    console.log(`  ${period}: ${images.length} images`);
    total += images.length;

    for (const { key, path, name } of images) {
        if (isDryRun) {
            console.log(`    [dry-run] ${path} -> ${BUCKET}/${key}`);
            continue;
        }
        const contentType = contentTypeForFile(name);
        try {
            execSync(
                `npx wrangler r2 object put "${BUCKET}/${key}" --file="${path}" --content-type="${contentType}" ${target}`,
                { stdio: "inherit", cwd: process.cwd() }
            );
            uploaded++;
        } catch {
            console.error(`    FAILED: ${path} -> ${BUCKET}/${key}`);
            failed++;
        }
    }
}

if (isDryRun) {
    console.log(`\nDry run — ${total} image(s) would be uploaded.`);
    process.exit(0);
}

console.log(`\nDone. Uploaded ${uploaded}/${total} image(s)${failed ? `, ${failed} failed` : ""}.`);
process.exit(failed ? 1 : 0);
