/**
 * Catalog-backed pluralization (client-safe — no server imports).
 *
 * The catalog carries `<base>_one` / `<base>_other` string pairs (e.g. `count.entries_one`
 * = "lançamento", `count.entries_other` = "lançamentos"). `plural` selects the form by the
 * common pt-BR rule (n === 1 → singular, else plural) and returns the localized noun; the
 * caller prepends the formatted number, e.g. `${n} ${plural(t, "count.entries", n)}`.
 *
 * No ICU/PluralRules dependency: the count nouns on the dashboard list pages all follow the
 * simple one/other rule, so a two-key select is sufficient and type-checked.
 */

import type { DeepCatalogKey } from "./catalog";

/** Catalog base keys that have `_one` / `_other` variants. */
export type PluralBase =
    | "count.entries"
    | "count.alerts"
    | "count.documents"
    | "count.fines"
    | "count.periods"
    | "count.units"
    | "count.vendors"
    | "count.runs"
    | "count.subcategories"
    | "count.rows";

/**
 * Return the localized noun for `n`, selecting the singular (`<base>_one`) form when `n === 1`
 * and the plural (`<base>_other`) form otherwise.
 *
 * @param t A translation function (`useTranslation()` on the client, or `t` from `@/lib/i18n`)
 * @param base The catalog base key (without the `_one`/`_other` suffix)
 * @param n The count driving the plural selection
 */
export function plural(t: (key: DeepCatalogKey) => string, base: PluralBase, n: number): string {
    const suffix = n === 1 ? "_one" : "_other";
    return t(`${base}${suffix}` as DeepCatalogKey);
}
