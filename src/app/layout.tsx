import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import { getLocale, t } from "@/lib/i18n";
import { LocaleProvider } from "@/lib/i18n/client";
import { ThemeProvider } from "@/components/theme-provider";
import "./globals.css";

const geistSans = Geist({
    variable: "--font-geist-sans",
    subsets: ["latin"],
});

const geistMono = Geist_Mono({
    variable: "--font-geist-mono",
    subsets: ["latin"],
});

export const metadata: Metadata = {
    title: t("app.title"),
    description: "Fiscal auditing tool for condominium SVHC",
};

export default function RootLayout({
    children,
}: Readonly<{
    children: React.ReactNode;
}>) {
    const locale = getLocale();

    return (
        <html lang={locale} suppressHydrationWarning>
            <body className={`${geistSans.variable} ${geistMono.variable} antialiased`}>
                <ThemeProvider attribute="class" defaultTheme="system" enableSystem disableTransitionOnChange>
                    <LocaleProvider locale={locale}>{children}</LocaleProvider>
                </ThemeProvider>
            </body>
        </html>
    );
}
