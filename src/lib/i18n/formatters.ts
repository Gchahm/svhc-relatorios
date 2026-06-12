/**
 * Centralized formatting helpers for locale-aware number, currency, date, and percentage formatting.
 * Server-default variants: when no `locale` is passed they resolve the active locale via the
 * server-only `getLocale()`. The pure, locale-explicit implementations live in `formatters.core.ts`
 * (client-safe); client components should use `formatters.client.ts` (always pass a locale).
 */

import { getLocale } from "./server";
import type { SupportedLocale } from "./catalog";
import {
    formatCurrencyFor,
    formatDateFor,
    formatDateTimeFor,
    formatDurationFor,
    formatNumberFor,
    formatPercentFor,
} from "./formatters.core";

/**
 * Get the current locale (for internal use in formatters)
 * In server components, uses getLocale()
 * In client components, formatters should be called from server components or passed locale explicitly
 */
function getCurrentLocale(): SupportedLocale {
    return getLocale();
}

/**
 * Format a number as currency for the active locale (R$ for pt-BR).
 *
 * @example
 * formatCurrency(1234.56) // => "R$ 1.234,56"
 */
export function formatCurrency(amount: number, locale?: SupportedLocale): string {
    return formatCurrencyFor(amount, locale || getCurrentLocale());
}

/**
 * Format a date as a localized string.
 *
 * @example
 * formatDate(new Date("2026-06-12")) // => "12/06/2026"
 */
export function formatDate(date: Date | string, locale?: SupportedLocale): string {
    return formatDateFor(date, locale || getCurrentLocale());
}

/**
 * Format a timestamp/date as a localized date-time string (date + hour:minute).
 *
 * @example
 * formatDateTime(1749700000000) // => "12/06/2026 03:46"
 */
export function formatDateTime(date: Date | string | number, locale?: SupportedLocale): string {
    return formatDateTimeFor(date, locale || getCurrentLocale());
}

/**
 * Format a decimal as a percentage.
 *
 * @example
 * formatPercent(0.7545, 2) // => "75,45%"
 */
export function formatPercent(value: number, decimals: number = 0, locale?: SupportedLocale): string {
    return formatPercentFor(value, decimals, locale || getCurrentLocale());
}

/**
 * Format a number with locale-appropriate separators.
 *
 * @example
 * formatNumber(1234.56) // => "1.234,56"
 */
export function formatNumber(value: number, decimals: number = 2, locale?: SupportedLocale): string {
    return formatNumberFor(value, decimals, locale || getCurrentLocale());
}

/**
 * Format a time duration in a human-readable way.
 *
 * @example
 * formatDuration(5400000) // => "1 hora, 30 minutos"
 */
export function formatDuration(milliseconds: number, locale?: SupportedLocale): string {
    return formatDurationFor(milliseconds, locale || getCurrentLocale());
}
