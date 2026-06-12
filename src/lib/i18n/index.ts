/**
 * Public i18n API
 * Server-side exports for use in server components and API routes
 */

import { getLocale } from "./server";
import { catalog, type SupportedLocale, type DeepCatalogKey } from "./catalog";

/**
 * Translate a catalog key in a server component
 *
 * Usage:
 * ```tsx
 * import { t } from "@/lib/i18n";
 *
 * export default function MyPage() {
 *   return <h1>{t("page.entries_title")}</h1>;
 * }
 * ```
 *
 * @param key - The catalog key to translate (type-checked at compile time)
 * @param locale - Optional locale override (defaults to pt-BR)
 * @returns The translated string
 * @throws Warns if key is not found; returns the key itself as fallback
 */
export function t(key: DeepCatalogKey, locale?: SupportedLocale): string {
    const activeLocale = locale || getLocale();
    const parts = key.split(".");

    let result: unknown = catalog[activeLocale];
    for (const part of parts) {
        if (typeof result === "object" && result !== null && part in result) {
            result = (result as Record<string, unknown>)[part];
        } else {
            // Key not found in active locale, try pt-BR fallback
            if (activeLocale !== "pt-BR") {
                result = catalog["pt-BR"];
                for (const p of parts) {
                    if (typeof result === "object" && result !== null && p in result) {
                        result = (result as Record<string, unknown>)[p];
                    } else {
                        // Key not found in fallback either
                        console.warn(
                            `[i18n] Translation key not found: "${key}" in locale "${activeLocale}" or fallback "pt-BR"`
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
}

/**
 * Get the active locale for the current request (server-side)
 *
 * Usage:
 * ```tsx
 * import { getLocale } from "@/lib/i18n";
 * export const dynamicParams = false;
 * export async function generateStaticParams() {
 *   const locale = getLocale();
 *   return [{ locale }];
 * }
 * ```
 */
export { getLocale };

/**
 * Get a localized alert type label by machine key
 *
 * Usage:
 * ```tsx
 * import { getAlertTypeLabel } from "@/lib/i18n";
 * const label = getAlertTypeLabel("attachment_amount_mismatch");
 * // => "Divergência de Valor"
 * ```
 */
export function getAlertTypeLabel(
    alertType: keyof (typeof catalog)["pt-BR"]["alert"]["types"],
    locale?: SupportedLocale
): string {
    return t(`alert.types.${alertType}` as DeepCatalogKey, locale);
}

/**
 * Re-export catalog and types for advanced usage
 */
export { catalog, type SupportedLocale, type CatalogShape, type DeepCatalogKey } from "./catalog";

/**
 * Re-export formatting helpers
 */
export { formatCurrency, formatDate, formatPercent, formatNumber, formatDuration } from "./formatters";

/**
 * Re-export client-side utilities (for use in client components)
 */
export { LocaleProvider, useTranslation, useLocale } from "./client";
