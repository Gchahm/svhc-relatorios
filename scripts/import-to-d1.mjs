#!/usr/bin/env node
/**
 * Import data from a JSON export file into the D1 database.
 *
 * Reads the JSON file produced by export-old-db.py, generates SQL INSERT
 * statements, and executes them via `wrangler d1 execute`.
 *
 * Usage:
 *   node scripts/import-to-d1.mjs [--input data/export.json] [--remote]
 *
 * Options:
 *   --input, -i   Path to the JSON export file (default: data/export.json)
 *   --remote      Apply to remote D1 (default: local)
 *   --dry-run     Generate SQL file without executing
 */

import { execSync } from "node:child_process";
import { readFileSync, writeFileSync, mkdirSync } from "node:fs";
import { parseArgs } from "node:util";

const { values: args } = parseArgs({
    options: {
        input: { type: "string", short: "i", default: "data/export.json" },
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
    "alerts",
];

function escapeSQL(value) {
    if (value === null || value === undefined) return "NULL";
    if (typeof value === "number") return String(value);
    if (typeof value === "boolean") return value ? "1" : "0";
    // Escape single quotes by doubling them
    const str = String(value).replace(/'/g, "''");
    return `'${str}'`;
}

function generateInserts(table, rows) {
    if (!rows || rows.length === 0) return "";

    const columns = Object.keys(rows[0]);
    const colList = columns.map((c) => `"${c}"`).join(", ");

    const statements = rows.map((row) => {
        const values = columns.map((col) => escapeSQL(row[col])).join(", ");
        return `INSERT INTO "${table}" (${colList}) VALUES (${values});`;
    });

    return statements.join("\n");
}

// Main
console.log(`Reading ${inputPath}...`);
const data = JSON.parse(readFileSync(inputPath, "utf-8"));

let allSQL = "PRAGMA defer_foreign_keys = ON;\n\n";

for (const table of TABLE_ORDER) {
    const rows = data[table];
    if (!rows || rows.length === 0) {
        console.log(`  ${table}: 0 rows (skipped)`);
        continue;
    }

    allSQL += `-- ${table} (${rows.length} rows)\n`;
    allSQL += generateInserts(table, rows);
    allSQL += "\n\n";
    console.log(`  ${table}: ${rows.length} rows`);
}

const totalRows = TABLE_ORDER.reduce((sum, t) => sum + (data[t]?.length || 0), 0);

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
