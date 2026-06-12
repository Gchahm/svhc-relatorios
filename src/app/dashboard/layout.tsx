export const dynamic = "force-dynamic";

import { initAuth } from "@/auth";
import { t } from "@/lib/i18n";
import { headers } from "next/headers";
import { redirect } from "next/navigation";
import Link from "next/link";
import SignOutButton from "./SignOutButton";
import UserMenu from "./UserMenu";
import {
    Receipt,
    BarChart3,
    FileSpreadsheet,
    FileText,
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
                <h1 className="text-2xl font-bold mb-2">{t("access.denied_title")}</h1>
                <p className="text-muted-foreground mb-6">{t("access.denied_message")}</p>
                <SignOutButton />
            </div>
        );
    }

    return (
        <div className="flex flex-col h-screen overflow-hidden font-[family-name:var(--font-geist-sans)]">
            <header className="w-full border-b shrink-0">
                <div className="mx-auto flex items-center justify-between px-4 py-2">
                    <Link href="/dashboard" className="text-sm font-semibold shrink-0">
                        SVHC Fiscal
                    </Link>

                    <nav className="flex items-center gap-1 mx-4">
                        {/* Financial */}
                        <NavLink href="/dashboard/reports" icon={<FileSpreadsheet className="h-3.5 w-3.5" />}>
                            {t("nav.reports")}
                        </NavLink>
                        <NavLink href="/dashboard/entries" icon={<Receipt className="h-3.5 w-3.5" />}>
                            {t("nav.entries")}
                        </NavLink>
                        <NavLink href="/dashboard/summary" icon={<BarChart3 className="h-3.5 w-3.5" />}>
                            {t("nav.summary")}
                        </NavLink>
                        <NavLink href="/dashboard/comparison" icon={<ArrowLeftRight className="h-3.5 w-3.5" />}>
                            {t("nav.comparison")}
                        </NavLink>

                        <div className="w-px h-4 bg-gray-200 mx-1" />

                        {/* Entities */}
                        <NavLink href="/dashboard/vendors" icon={<Store className="h-3.5 w-3.5" />}>
                            {t("nav.vendors")}
                        </NavLink>
                        <NavLink href="/dashboard/documents" icon={<FileText className="h-3.5 w-3.5" />}>
                            {t("nav.documents")}
                        </NavLink>
                        <NavLink href="/dashboard/units" icon={<Building2 className="h-3.5 w-3.5" />}>
                            {t("nav.units")}
                        </NavLink>
                        <NavLink href="/dashboard/fines" icon={<Gavel className="h-3.5 w-3.5" />}>
                            {t("nav.fines")}
                        </NavLink>

                        <div className="w-px h-4 bg-gray-200 mx-1" />

                        {/* Analysis */}
                        <NavLink href="/dashboard/alerts" icon={<AlertTriangle className="h-3.5 w-3.5" />}>
                            {t("nav.alerts")}
                        </NavLink>

                        <div className="w-px h-4 bg-gray-200 mx-1" />

                        {/* System */}
                        <NavLink href="/dashboard/scrape-runs" icon={<RefreshCw className="h-3.5 w-3.5" />}>
                            {t("nav.runs")}
                        </NavLink>
                    </nav>

                    <UserMenu
                        name={session.user?.name || session.user?.email || "User"}
                        email={session.user?.email || ""}
                    />
                </div>
            </header>

            <main className="flex-1 flex flex-col items-center p-8 min-h-0 overflow-auto">
                <div className="w-full max-w-6xl flex-1 flex flex-col min-h-0">{children}</div>
            </main>
        </div>
    );
}

function NavLink({ href, icon, children }: { href: string; icon: React.ReactNode; children: React.ReactNode }) {
    return (
        <Link
            href={href}
            className="flex items-center gap-1 px-2 py-1 rounded text-sm text-gray-600 hover:text-gray-900 hover:bg-gray-100 transition-colors"
        >
            {icon}
            {children}
        </Link>
    );
}
