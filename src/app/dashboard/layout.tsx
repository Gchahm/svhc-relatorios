export const dynamic = "force-dynamic";

import { initAuth } from "@/auth";
import { headers } from "next/headers";
import { redirect } from "next/navigation";
import Link from "next/link";
import SignOutButton from "./SignOutButton";
import {
    Receipt,
    BarChart3,
    FileSpreadsheet,
    Store,
    Building2,
    AlertTriangle,
    ArrowLeftRight,
    Gavel,
    RefreshCw,
} from "lucide-react";

export default async function DashboardLayout({ children }: { children: React.ReactNode }) {
    const authInstance = await initAuth();
    const session = await authInstance.api.getSession({ headers: await headers() });

    if (!session) {
        redirect("/");
    }

    const allowedRoles = ["admin", "member"];
    const userRole = (session.user as { role?: string }).role;
    if (!userRole || !allowedRoles.includes(userRole)) {
        return (
            <div className="flex flex-col items-center justify-center min-h-screen font-[family-name:var(--font-geist-sans)] p-8 text-center">
                <h1 className="text-2xl font-bold mb-2">Access Denied</h1>
                <p className="text-muted-foreground mb-6">
                    Your account is pending approval. Contact an administrator to get access.
                </p>
                <SignOutButton />
            </div>
        );
    }

    return (
        <div className="flex flex-col h-screen overflow-hidden font-[family-name:var(--font-geist-sans)]">
            <header className="w-full border-b shrink-0">
                <div className="max-w-3xl mx-auto flex items-center justify-between px-8 py-2">
                    <nav className="flex items-center gap-4">
                        <Link href="/dashboard" className="text-sm font-semibold mr-2">
                            SVHC Fiscal
                        </Link>
                        <Link
                            href="/dashboard/reports"
                            className="flex items-center gap-1 text-sm text-gray-600 hover:text-gray-900 transition-colors"
                        >
                            <FileSpreadsheet className="h-3.5 w-3.5" />
                            Reports
                        </Link>
                        <Link
                            href="/dashboard/entries"
                            className="flex items-center gap-1 text-sm text-gray-600 hover:text-gray-900 transition-colors"
                        >
                            <Receipt className="h-3.5 w-3.5" />
                            Entries
                        </Link>
                        <Link
                            href="/dashboard/summary"
                            className="flex items-center gap-1 text-sm text-gray-600 hover:text-gray-900 transition-colors"
                        >
                            <BarChart3 className="h-3.5 w-3.5" />
                            Summary
                        </Link>
                        <Link
                            href="/dashboard/vendors"
                            className="flex items-center gap-1 text-sm text-gray-600 hover:text-gray-900 transition-colors"
                        >
                            <Store className="h-3.5 w-3.5" />
                            Vendors
                        </Link>
                        <Link
                            href="/dashboard/units"
                            className="flex items-center gap-1 text-sm text-gray-600 hover:text-gray-900 transition-colors"
                        >
                            <Building2 className="h-3.5 w-3.5" />
                            Units
                        </Link>
                        <Link
                            href="/dashboard/fines"
                            className="flex items-center gap-1 text-sm text-gray-600 hover:text-gray-900 transition-colors"
                        >
                            <Gavel className="h-3.5 w-3.5" />
                            Fines
                        </Link>
                        <Link
                            href="/dashboard/alerts"
                            className="flex items-center gap-1 text-sm text-gray-600 hover:text-gray-900 transition-colors"
                        >
                            <AlertTriangle className="h-3.5 w-3.5" />
                            Alerts
                        </Link>
                        <Link
                            href="/dashboard/comparison"
                            className="flex items-center gap-1 text-sm text-gray-600 hover:text-gray-900 transition-colors"
                        >
                            <ArrowLeftRight className="h-3.5 w-3.5" />
                            Comparativo
                        </Link>
                        <Link
                            href="/dashboard/scrape-runs"
                            className="flex items-center gap-1 text-sm text-gray-600 hover:text-gray-900 transition-colors"
                        >
                            <RefreshCw className="h-3.5 w-3.5" />
                            Runs
                        </Link>
                    </nav>
                    <div className="flex items-center gap-2">
                        <span className="text-sm text-gray-600">{session.user?.name || session.user?.email}</span>
                        <SignOutButton />
                    </div>
                </div>
            </header>

            <main className="flex-1 flex flex-col items-center p-8 min-h-0 overflow-auto">
                <div className="w-full max-w-6xl flex-1 flex flex-col min-h-0">{children}</div>
            </main>
        </div>
    );
}
