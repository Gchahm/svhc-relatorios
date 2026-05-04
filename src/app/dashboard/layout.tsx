import { initAuth } from "@/auth";
import { headers } from "next/headers";
import { redirect } from "next/navigation";
import Link from "next/link";
import SignOutButton from "./SignOutButton";
import { Github, Package, FileText, User, MapPin, Upload } from "lucide-react";

export default async function DashboardLayout({ children }: { children: React.ReactNode }) {
    const authInstance = await initAuth();
    const session = await authInstance.api.getSession({ headers: await headers() });

    if (!session) {
        redirect("/");
    }

    const openAPISpec = await authInstance.api.generateOpenAPISchema();

    return (
        <div className="flex flex-col min-h-screen font-[family-name:var(--font-geist-sans)]">
            <header className="w-full border-b">
                <div className="max-w-3xl mx-auto flex items-center justify-between px-8 py-4">
                    <div>
                        <h1 className="text-xl font-bold">Dashboard</h1>
                        <p className="text-xs text-gray-500">Powered by better-auth-cloudflare</p>
                    </div>
                    <div className="flex items-center gap-2">
                        <span className="text-sm text-gray-600">
                            {session.user?.name || session.user?.email || "Anonymous User"}
                        </span>
                        <SignOutButton />
                    </div>
                </div>
                <nav className="max-w-3xl mx-auto px-8 pb-2">
                    <div className="flex gap-4">
                        <Link
                            href="/dashboard/user-info"
                            className="flex items-center gap-1.5 text-sm text-gray-600 hover:text-gray-900 transition-colors"
                        >
                            <User className="h-4 w-4" />
                            User Info
                        </Link>
                        <Link
                            href="/dashboard/geolocation"
                            className="flex items-center gap-1.5 text-sm text-gray-600 hover:text-gray-900 transition-colors"
                        >
                            <MapPin className="h-4 w-4" />
                            Geolocation
                        </Link>
                        <Link
                            href="/dashboard/file-upload"
                            className="flex items-center gap-1.5 text-sm text-gray-600 hover:text-gray-900 transition-colors"
                        >
                            <Upload className="h-4 w-4" />
                            File Upload
                        </Link>
                    </div>
                </nav>
            </header>

            <main className="flex-1 flex flex-col items-center p-8">
                <div className="w-full max-w-3xl">{children}</div>
            </main>

            <footer className="w-full text-center text-sm text-gray-500 py-4 mt-8">
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
