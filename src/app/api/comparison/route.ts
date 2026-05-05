import { initAuth } from "@/auth";
import { getDb } from "@/db";
import { categorySubtotals, subcategories, categories, accountabilityReports } from "@/db/fiscal.schema";
import { eq } from "drizzle-orm";
import { headers } from "next/headers";
import { type NextRequest, NextResponse } from "next/server";

const ALLOWED_ROLES = ["admin", "member"];

interface SubtotalRow {
    category: string;
    subcategory: string;
    movementType: string;
    amount: number;
}

export async function GET(request: NextRequest) {
    const authInstance = await initAuth();
    const session = await authInstance.api.getSession({ headers: await headers() });
    const userRole = (session?.user as { role?: string } | undefined)?.role;
    if (!session || !userRole || !ALLOWED_ROLES.includes(userRole)) {
        return NextResponse.json({ error: "Unauthorized" }, { status: 403 });
    }

    const p1 = request.nextUrl.searchParams.get("p1");
    const p2 = request.nextUrl.searchParams.get("p2");

    if (!p1 || !p2) {
        return NextResponse.json({ error: "Query parameters p1 and p2 are required" }, { status: 400 });
    }

    const db = await getDb();

    async function getSubtotalsForPeriod(period: string): Promise<SubtotalRow[]> {
        return db
            .select({
                category: categories.name,
                subcategory: subcategories.name,
                movementType: categorySubtotals.movementType,
                amount: categorySubtotals.amount,
            })
            .from(categorySubtotals)
            .innerJoin(accountabilityReports, eq(categorySubtotals.reportId, accountabilityReports.id))
            .innerJoin(subcategories, eq(categorySubtotals.subcategoryId, subcategories.id))
            .innerJoin(categories, eq(subcategories.categoryId, categories.id))
            .where(eq(accountabilityReports.period, period))
            .orderBy(categories.name, subcategories.name);
    }

    const [rowsP1, rowsP2] = await Promise.all([getSubtotalsForPeriod(p1), getSubtotalsForPeriod(p2)]);

    // Merge by (category, subcategory, movementType) key
    type MergedKey = string;
    const map = new Map<
        MergedKey,
        { category: string; subcategory: string; movementType: string; valueP1: number; valueP2: number }
    >();

    for (const row of rowsP1) {
        const key = `${row.category}|||${row.subcategory}|||${row.movementType}`;
        const existing = map.get(key);
        if (existing) {
            existing.valueP1 += row.amount;
        } else {
            map.set(key, {
                category: row.category,
                subcategory: row.subcategory,
                movementType: row.movementType,
                valueP1: row.amount,
                valueP2: 0,
            });
        }
    }

    for (const row of rowsP2) {
        const key = `${row.category}|||${row.subcategory}|||${row.movementType}`;
        const existing = map.get(key);
        if (existing) {
            existing.valueP2 += row.amount;
        } else {
            map.set(key, {
                category: row.category,
                subcategory: row.subcategory,
                movementType: row.movementType,
                valueP1: 0,
                valueP2: row.amount,
            });
        }
    }

    const result = Array.from(map.values())
        .sort((a, b) => {
            const catCmp = a.category.localeCompare(b.category);
            if (catCmp !== 0) return catCmp;
            return a.subcategory.localeCompare(b.subcategory);
        })
        .map(row => {
            const diff = row.valueP2 - row.valueP1;
            const pctChange = row.valueP1 !== 0 ? (diff / row.valueP1) * 100 : null;
            return {
                category: row.category,
                subcategory: row.subcategory,
                movementType: row.movementType,
                valueP1: row.valueP1,
                valueP2: row.valueP2,
                diff,
                pctChange,
            };
        });

    return NextResponse.json(result);
}
