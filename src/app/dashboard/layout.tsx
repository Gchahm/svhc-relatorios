export const dynamic = "force-dynamic";

import { initAuth } from "@/auth";
import { headers } from "next/headers";
import { redirect } from "next/navigation";
import Link from "next/link";
import SignOutButton from "./SignOutButton";
import { Github, Package, FileText, User, MapPin, Receipt } from "lucide-react";

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

    const openAPISpec = await authInstance.api.generateOpenAPISchema();

    return (
        <div className="flex flex-col h-screen overflow-hidden font-[family-name:var(--font-geist-sans)]">
            <header className="w-full border-b shrink-0">
                <div className="max-w-3xl mx-auto flex items-center justify-between px-8 py-2">
                    <nav className="flex items-center gap-4">
                        <Link href="/dashboard" className="text-sm font-semibold mr-2">
                            Dashboard
                        </Link>
                        <Link
                            href="/dashboard/user-info"
                            className="flex items-center gap-1 text-sm text-gray-600 hover:text-gray-900 transition-colors"
                        >
                            <User className="h-3.5 w-3.5" />
                            User Info
                        </Link>
                        <Link
                            href="/dashboard/geolocation"
                            className="flex items-center gap-1 text-sm text-gray-600 hover:text-gray-900 transition-colors"
                        >
                            <MapPin className="h-3.5 w-3.5" />
                            Geolocation
                        </Link>
                        <Link
                            href="/dashboard/entries"
                            className="flex items-center gap-1 text-sm text-gray-600 hover:text-gray-900 transition-colors"
                        >
                            <Receipt className="h-3.5 w-3.5" />
                            Entries
                        </Link>
                    </nav>
                    <div className="flex items-center gap-2">
                        <span className="text-sm text-gray-600">{session.user?.name || session.user?.email}</span>
                        <SignOutButton />
                    </div>
                </div>
            </header>

            <main className="flex-1 flex flex-col items-center p-8 min-h-0 overflow-auto">
                <div className="w-full max-w-3xl flex-1 flex flex-col min-h-0">{children}</div>
            </main>

            <footer className="w-full text-center text-sm text-gray-500 py-4 shrink-0">
                <div className="space-y-3">
                    <div>Powered by better-auth-cloudflare</div>
                    <div className="flex items-center justify-center gap-4">
                        <a
                            href="https://github.com/zpg6/better-auth-cloudflare"
                            target="_blank"
                            rel="noopener noreferrer"
                            className="flex items-center gap-1 hover:text-gray-700 transition-colors"
                        >
                            <Github size={16} />
                            <span>GitHub</span>
                        </a>
                        <a
                            href="https://www.npmjs.com/package/better-auth-cloudflare"
                            target="_blank"
                            rel="noopener noreferrer"
                            className="flex items-center gap-1 hover:text-gray-700 transition-colors"
                        >
                            <Package size={16} />
                            <span>npm</span>
                        </a>
                        <Link
                            href="/api/auth/reference#tag/cloudflare/get/cloudflare/geolocation"
                            className="flex items-center gap-1 hover:text-gray-700 transition-colors"
                            title={`OpenAPI v${openAPISpec.openapi} Schema`}
                        >
                            <FileText size={16} />
                            <span>OpenAPI</span>
                        </Link>
                    </div>
                </div>
            </footer>
        </div>
    );
}
