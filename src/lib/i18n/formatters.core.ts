/**
 * Pure, locale-explicit formatting core (client-safe — NO server imports).
 *
 * These functions take an explicit `SupportedLocale` and contain only `Intl.*` + string logic,
 * so they can be imported from client components without dragging in `@opennextjs/cloudflare`
 * (`getCloudflareContext`). The server-default wrappers in `formatters.ts` and the client wrappers
 * in `formatters.client.ts` both delegate here, keeping a single formatting implementation.
 */

import type { SupportedLocale } from "./catalog";

function intlLocale(locale: SupportedLocale): string {
    return locale === "pt-BR" ? "pt-BR" : "en-US";
}

export function formatCurrencyFor(amount: number, locale: SupportedLocale): string {
    return new Intl.NumberFormat(intlLocale(locale), {
        style: "currency",
        currency: locale === "pt-BR" ? "BRL" : "USD",
    }).format(amount);
}

export function formatDateFor(date: Date | string, locale: SupportedLocale): string {
    const dateObj = typeof date === "string" ? new Date(date) : date;
    return new Intl.DateTimeFormat(intlLocale(locale), {
        day: "2-digit",
        month: "2-digit",
        year: "numeric",
    }).format(dateObj);
}

export function formatDateTimeFor(date: Date | string | number, locale: SupportedLocale): string {
    const dateObj = typeof date === "number" || typeof date === "string" ? new Date(date) : date;
    return new Intl.DateTimeFormat(intlLocale(locale), {
        day: "2-digit",
        month: "2-digit",
        year: "numeric",
        hour: "2-digit",
        minute: "2-digit",
    }).format(dateObj);
}

export function formatPercentFor(value: number, decimals: number, locale: SupportedLocale): string {
    return new Intl.NumberFormat(intlLocale(locale), {
        style: "percent",
        minimumFractionDigits: decimals,
        maximumFractionDigits: decimals,
    }).format(value);
}

export function formatNumberFor(value: number, decimals: number, locale: SupportedLocale): string {
    return new Intl.NumberFormat(intlLocale(locale), {
        minimumFractionDigits: decimals,
        maximumFractionDigits: decimals,
    }).format(value);
}

export function formatDurationFor(milliseconds: number, locale: SupportedLocale): string {
    const seconds = Math.floor(milliseconds / 1000);
    const minutes = Math.floor(seconds / 60);
    const hours = Math.floor(minutes / 60);
    const days = Math.floor(hours / 24);

    const isPtBr = locale === "pt-BR";

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
