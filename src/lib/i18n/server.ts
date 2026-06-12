/**
 * Server-side i18n utilities
 * Used in server components and API routes to resolve the active locale
 */

import { getCloudflareContext } from "@opennextjs/cloudflare";
import type { SupportedLocale } from "./catalog";

/**
 * Get the active locale for the current request (server-side)
 * Reads from Cloudflare context or defaults to pt-BR
 *
 * Usage in server components:
 * ```tsx
 * import { getLocale } from "@/lib/i18n/server";
 *
 * export default function Header() {
 *   const locale = getLocale();
 *   return <h1>{t("nav.home")}</h1>;
 * }
 * ```
 */
export function getLocale(): SupportedLocale {
    try {
        getCloudflareContext();
        // Future: read from cookies or request headers
        // For now, always default to pt-BR
        return "pt-BR";
    } catch {
        // Fallback when not in Cloudflare context (e.g., local dev)
        return "pt-BR";
    }
}
