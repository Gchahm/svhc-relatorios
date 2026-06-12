/**
 * Client-side i18n context and hooks
 * Provides LocaleProvider and useTranslation for client components
 */

"use client";

import React, { createContext, useContext } from "react";
import type { SupportedLocale, DeepCatalogKey, CatalogShape } from "./catalog";
import { catalog } from "./catalog";

/**
 * LocaleContext for client-side locale management
 */
interface LocaleContextValue {
    locale: SupportedLocale;
    setLocale?: (locale: SupportedLocale) => void;
}

const LocaleContext = createContext<LocaleContextValue | null>(null);

/**
 * Props for LocaleProvider
 */
interface LocaleProviderProps {
    children: React.ReactNode;
    locale: SupportedLocale;
}

/**
 * LocaleProvider component - wrap your app or layout with this to provide locale context
 *
 * Usage in root layout (server component that passes locale to client):
 * ```tsx
 * import { LocaleProvider } from "@/lib/i18n/client";
 * import { getLocale } from "@/lib/i18n/server";
 *
 * export default function RootLayout({ children }) {
 *   const locale = getLocale();
 *   return (
 *     <html lang={locale}>
 *       <body>
 *         <LocaleProvider locale={locale}>
 *           {children}
 *         </LocaleProvider>
 *       </body>
 *     </html>
 *   );
 * }
 * ```
 */
export function LocaleProvider({ children, locale }: LocaleProviderProps) {
    return <LocaleContext.Provider value={{ locale }}>{children}</LocaleContext.Provider>;
}

/**
 * useTranslation hook - use in client components to get the translation function
 *
 * Usage in client component:
 * ```tsx
 * "use client";
 * import { useTranslation } from "@/lib/i18n/client";
 *
 * export function Button() {
 *   const t = useTranslation();
 *   return <button>{t("button.submit")}</button>;
 * }
 * ```
 *
 * @returns A translation function that accepts a catalog key and returns the localized string
 * @throws If used outside of LocaleProvider
 */
export function useTranslation() {
    const context = useContext(LocaleContext);

    if (!context) {
        throw new Error(
            "useTranslation must be used within a LocaleProvider. " +
                "Make sure your root layout wraps the app with <LocaleProvider>."
        );
    }

    return (key: DeepCatalogKey): string => {
        const { locale } = context;
        const parts = key.split(".");

        let result: unknown = catalog[locale];
        for (const part of parts) {
            if (typeof result === "object" && result !== null && part in result) {
                result = (result as Record<string, unknown>)[part];
            } else {
                // Key not found in active locale, try pt-BR fallback
                if (locale !== "pt-BR") {
                    result = catalog["pt-BR"];
                    for (const p of parts) {
                        if (typeof result === "object" && result !== null && p in result) {
                            result = (result as Record<string, unknown>)[p];
                        } else {
                            // Key not found in fallback either
                            console.warn(
                                `[i18n] Translation key not found: "${key}" in locale "${locale}" or fallback "pt-BR"`
                            );
                            return key;
                        }
                    }
                } else {
                    console.warn(`[i18n] Translation key not found: "${key}" in locale "pt-BR"`);
                    return key;
                }
                break;
            }
        }

        if (typeof result === "string") {
            return result;
        }

        console.warn(`[i18n] Translation key resolved to non-string: "${key}"`);
        return key;
    };
}

/**
 * useLocale hook - get the current active locale
 *
 * Usage in client component:
 * ```tsx
 * "use client";
 * import { useLocale } from "@/lib/i18n/client";
 *
 * export function LocaleDisplay() {
 *   const locale = useLocale();
 *   return <span>Current locale: {locale}</span>;
 * }
 * ```
 *
 * @returns The current active locale
 * @throws If used outside of LocaleProvider
 */
export function useLocale(): SupportedLocale {
    const context = useContext(LocaleContext);

    if (!context) {
        throw new Error(
            "useLocale must be used within a LocaleProvider. " +
                "Make sure your root layout wraps the app with <LocaleProvider>."
        );
    }

    return context.locale;
}
