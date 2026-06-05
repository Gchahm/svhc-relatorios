#!/usr/bin/env node
/**
 * Import data from JSON files into the D1 database.
 *
 * Reads JSON files (single file or directory of per-period files) and
 * executes SQL INSERT statements via `wrangler d1 execute`.
 *
 * All tables use INSERT OR REPLACE (upsert) so re-importing the same
 * data safely overwrites existing rows.
 *
 * Usage:
 *   node scripts/import-to-d1.mjs [--input data/scrape] [--remote]
 *   node scripts/import-to-d1.mjs --input data/export.json [--remote]
 */

import { execSync } from "node:child_process";
import { readFileSync, writeFileSync, readdirSync, statSync, mkdirSync } from "node:fs";
import { parseArgs } from "node:util";
import { join } from "node:path";

const { values: args } = parseArgs({
    options: {
        input: { type: "string", short: "i", default: "data/scrape" },
        remote: { type: "boolean", default: false },
        "dry-run": { type: "boolean", default: false },
    },
});

const inputPath = args.input;
const isRemote = args.remote;
const isDryRun = args["dry-run"];

// Table insertion order (respects foreign key dependencies)
const TABLE_ORDER = [
    "scrape_runs",
    "categories",
    "vendors",
    "units",
    "subcategories",
    "accountability_reports",
    "entries",
    "category_subtotals",
    "approvers",
    "documents",
    "document_analyses",
    "document_analysis_records",
    "alerts",
];

function escapeSQL(value) {
    if (value === null || value === undefined) return "NULL";
    if (typeof value === "number") return String(value);
    if (typeof value === "boolean") return value ? "1" : "0";
    // Objects/arrays (e.g. a record's structured `response`) must be JSON-serialized,
    // not coerced via String() — which would silently store "[object Object]".
    if (typeof value === "object") {
        const json = JSON.stringify(value).replace(/'/g, "''");
        return `'${json}'`;
    }
    const str = String(value).replace(/'/g, "''");
    return `'${str}'`;
}

function generateInserts(table, rows) {
    if (!rows || rows.length === 0) return "";

    const columns = Object.keys(rows[0]);
    const colList = columns.map(c => `"${c}"`).join(", ");

    const statements = rows.map(row => {
        const values = columns.map(col => escapeSQL(row[col])).join(", ");
        return `INSERT OR REPLACE INTO "${table}" (${colList}) VALUES (${values});`;
    });

    return statements.join("\n");
}

function loadJsonFiles(inputPath) {
    const stat = statSync(inputPath);

    if (stat.isFile()) {
        console.log(`Reading ${inputPath}...`);
        return [JSON.parse(readFileSync(inputPath, "utf-8"))];
    }

    if (stat.isDirectory()) {
        const files = readdirSync(inputPath)
            .filter(f => f.endsWith(".json"))
            .sort();
        console.log(`Reading ${files.length} JSON files from ${inputPath}/...`);
        return files.map(f => {
            const path = join(inputPath, f);
            console.log(`  ${f}`);
            return JSON.parse(readFileSync(path, "utf-8"));
        });
    }

    throw new Error(`Input path is neither a file nor a directory: ${inputPath}`);
}

// Main
const datasets = loadJsonFiles(inputPath);

// Merge all datasets, deduplicating reference tables by id
const merged = {};
const seenIds = {};

for (const table of TABLE_ORDER) {
    merged[table] = [];
    seenIds[table] = new Set();
}

for (const data of datasets) {
    for (const table of TABLE_ORDER) {
        const rows = data[table];
        if (!rows) continue;
        for (const row of rows) {
            const id = row.id;
            if (id && seenIds[table].has(id)) continue;
            if (id) seenIds[table].add(id);

            // Per-page analysis records are nested under their document analysis in
            // the period JSON; lift them into the normalized table (document_analyses
            // precedes document_analysis_records in TABLE_ORDER) and strip the nested
            // key so the parent INSERT only carries real columns.
            if (table === "document_analyses" && Array.isArray(row.analysis_records)) {
                for (const rec of row.analysis_records) {
                    if (rec.id && seenIds["document_analysis_records"].has(rec.id)) continue;
                    if (rec.id) seenIds["document_analysis_records"].add(rec.id);
                    merged["document_analysis_records"].push(rec);
                }
                delete row.analysis_records;
            }

            merged[table].push(row);
        }
    }
}

let allSQL = "PRAGMA defer_foreign_keys = ON;\n\n";

for (const table of TABLE_ORDER) {
    const rows = merged[table];
    if (!rows || rows.length === 0) {
        console.log(`  ${table}: 0 rows (skipped)`);
        continue;
    }

    allSQL += `-- ${table} (${rows.length} rows)\n`;
    allSQL += generateInserts(table, rows);
    allSQL += "\n\n";
    console.log(`  ${table}: ${rows.length} rows`);
}

const totalRows = TABLE_ORDER.reduce((sum, t) => sum + (merged[t]?.length || 0), 0);

// Write SQL to temp file
mkdirSync("data", { recursive: true });
const sqlPath = "data/import.sql";
writeFileSync(sqlPath, allSQL, "utf-8");
console.log(`\nGenerated ${sqlPath} (${totalRows} total rows)`);

if (isDryRun) {
    console.log("Dry run — SQL file written but not executed.");
    process.exit(0);
}

// Execute via wrangler
const target = isRemote ? "--remote" : "--local";
console.log(`\nExecuting against D1 (${isRemote ? "remote" : "local"})...`);

try {
    execSync(`npx wrangler d1 execute DATABASE --file=${sqlPath} ${target}`, {
        stdio: "inherit",
        cwd: process.cwd(),
    });
    console.log("\nImport complete!");
} catch (error) {
    console.error("\nImport failed. Check the SQL file at", sqlPath);
    process.exit(1);
}
