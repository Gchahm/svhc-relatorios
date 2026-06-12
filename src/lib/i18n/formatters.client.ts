/**
 * Client-safe formatters — locale-explicit, NO server imports.
 *
 * Client components import these and pass the active locale from `useLocale()` (from
 * `@/lib/i18n/client`). Same formatting behavior as the server-default `formatters.ts`, but
 * without pulling in `@opennextjs/cloudflare` (`getCloudflareContext`) — so it never drags
 * server-only code into the client bundle.
 *
 * @example
 * const locale = useLocale();
 * formatCurrency(1234.56, locale); // => "R$ 1.234,56" (pt-BR)
 */

import type { SupportedLocale } from "./catalog";
import {
    formatCurrencyFor,
    formatDateFor,
    formatDateTimeFor,
    formatDurationFor,
    formatNumberFor,
    formatPercentFor,
} from "./formatters.core";

export function formatCurrency(amount: number, locale: SupportedLocale): string {
    return formatCurrencyFor(amount, locale);
}

export function formatDate(date: Date | string, locale: SupportedLocale): string {
    return formatDateFor(date, locale);
}

export function formatDateTime(date: Date | string | number, locale: SupportedLocale): string {
    return formatDateTimeFor(date, locale);
}

export function formatPercent(value: number, decimals: number, locale: SupportedLocale): string {
    return formatPercentFor(value, decimals, locale);
}

export function formatNumber(value: number, decimals: number, locale: SupportedLocale): string {
    return formatNumberFor(value, decimals, locale);
}

export function formatDuration(milliseconds: number, locale: SupportedLocale): string {
    return formatDurationFor(milliseconds, locale);
}
