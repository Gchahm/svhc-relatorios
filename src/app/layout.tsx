import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import { getLocale, LocaleProvider, t } from "@/lib/i18n";
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
    title: "SVHC Fiscal",
    description: "Fiscal auditing tool for condominium SVHC",
};

export default function RootLayout({
    children,
}: Readonly<{
    children: React.ReactNode;
}>) {
    const locale = getLocale();

    return (
        <html lang={locale}>
            <body className={`${geistSans.variable} ${geistMono.variable} antialiased`}>
                <LocaleProvider locale={locale}>{children}</LocaleProvider>
            </body>
        </html>
    );
}
