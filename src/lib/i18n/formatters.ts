/**
 * Centralized formatting helpers for locale-aware number, currency, date, and percentage formatting
 * All functions derive the active locale from the i18n layer
 */

import { getLocale } from "./server";
import type { SupportedLocale } from "./catalog";

/**
 * Get the current locale (for internal use in formatters)
 * In server components, uses getLocale()
 * In client components, formatters should be called from server components or passed locale explicitly
 */
function getCurrentLocale(): SupportedLocale {
    return getLocale();
}

/**
 * Format a number as Brazilian currency (R$ format)
 *
 * @param amount The numeric amount to format
 * @param locale Optional locale override (defaults to pt-BR)
 * @returns Formatted currency string, e.g., "R$ 1.234,56"
 *
 * @example
 * formatCurrency(1234.56) // => "R$ 1.234,56"
 * formatCurrency(100) // => "R$ 100,00"
 */
export function formatCurrency(amount: number, locale?: SupportedLocale): string {
    const activeLocale = locale || getCurrentLocale();
    return new Intl.NumberFormat(activeLocale === "pt-BR" ? "pt-BR" : "en-US", {
        style: "currency",
        currency: activeLocale === "pt-BR" ? "BRL" : "USD",
    }).format(amount);
}

/**
 * Format a date as a localized string
 *
 * @param date The date to format
 * @param locale Optional locale override (defaults to pt-BR)
 * @returns Formatted date string, e.g., "12/06/2026" (pt-BR) or "06/12/2026" (en)
 *
 * @example
 * formatDate(new Date("2026-06-12")) // => "12/06/2026"
 */
export function formatDate(date: Date | string, locale?: SupportedLocale): string {
    const activeLocale = locale || getCurrentLocale();
    const dateObj = typeof date === "string" ? new Date(date) : date;

    return new Intl.DateTimeFormat(activeLocale === "pt-BR" ? "pt-BR" : "en-US", {
        day: "2-digit",
        month: "2-digit",
        year: "numeric",
    }).format(dateObj);
}

/**
 * Format a decimal as a percentage
 *
 * @param value The decimal value (e.g., 0.75 for 75%)
 * @param decimals Optional number of decimal places (default: 0)
 * @param locale Optional locale override (defaults to pt-BR)
 * @returns Formatted percentage string, e.g., "75%" or "75,50%" (pt-BR)
 *
 * @example
 * formatPercent(0.75) // => "75%"
 * formatPercent(0.7545, 2) // => "75,45%"
 */
export function formatPercent(value: number, decimals: number = 0, locale?: SupportedLocale): string {
    const activeLocale = locale || getCurrentLocale();
    const formatted = new Intl.NumberFormat(activeLocale === "pt-BR" ? "pt-BR" : "en-US", {
        style: "percent",
        minimumFractionDigits: decimals,
        maximumFractionDigits: decimals,
    }).format(value);

    return formatted;
}

/**
 * Format a number with thousands separator and decimal separator appropriate for the locale
 *
 * @param value The number to format
 * @param decimals Optional number of decimal places (default: 2)
 * @param locale Optional locale override (defaults to pt-BR)
 * @returns Formatted number string, e.g., "1.234,56" (pt-BR) or "1,234.56" (en)
 *
 * @example
 * formatNumber(1234.56) // => "1.234,56"
 * formatNumber(1000000, 3) // => "1.000.000,000"
 */
export function formatNumber(value: number, decimals: number = 2, locale?: SupportedLocale): string {
    const activeLocale = locale || getCurrentLocale();
    return new Intl.NumberFormat(activeLocale === "pt-BR" ? "pt-BR" : "en-US", {
        minimumFractionDigits: decimals,
        maximumFractionDigits: decimals,
    }).format(value);
}

/**
 * Format a time duration in a human-readable way
 *
 * @param milliseconds The duration in milliseconds
 * @param locale Optional locale override (defaults to pt-BR)
 * @returns Human-readable duration, e.g., "1 hora, 30 minutos" (pt-BR)
 *
 * @example
 * formatDuration(5400000) // => "1 hora, 30 minutos"
 */
export function formatDuration(milliseconds: number, locale?: SupportedLocale): string {
    const activeLocale = locale || getCurrentLocale();
    const seconds = Math.floor(milliseconds / 1000);
    const minutes = Math.floor(seconds / 60);
    const hours = Math.floor(minutes / 60);
    const days = Math.floor(hours / 24);

    const isPtBr = activeLocale === "pt-BR";

    if (days > 0) {
        return isPtBr
            ? `${days} dia${days > 1 ? "s" : ""}, ${hours % 24} hora${hours % 24 > 1 ? "s" : ""}`
            : `${days} day${days > 1 ? "s" : ""}, ${hours % 24} hour${hours % 24 > 1 ? "s" : ""}`;
    }

    if (hours > 0) {
        return isPtBr
            ? `${hours} hora${hours > 1 ? "s" : ""}, ${minutes % 60} minuto${minutes % 60 > 1 ? "s" : ""}`
            : `${hours} hour${hours > 1 ? "s" : ""}, ${minutes % 60} minute${minutes % 60 > 1 ? "s" : ""}`;
    }

    if (minutes > 0) {
        return isPtBr ? `${minutes} minuto${minutes > 1 ? "s" : ""}` : `${minutes} minute${minutes > 1 ? "s" : ""}`;
    }

    return isPtBr ? `${seconds} segundo${seconds > 1 ? "s" : ""}` : `${seconds} second${seconds > 1 ? "s" : ""}`;
}
