# Research: I18N-004 Detail-surface localization

## Decision 1 — Client-safe i18n entrypoints

**Decision**: All four edited components are `"use client"`, so they import the translation hook from
`@/lib/i18n/client` (`useTranslation`, `useLocale`, `useAlertTypeLabel`) and the formatters from
`@/lib/i18n/formatters.client` (passing the active locale from `useLocale()`).

**Rationale**: The server barrel `@/lib/i18n` pulls in `./server` (`getCloudflareContext`); importing
it from a client component drags server-only code into the client bundle. The barrel's own comment and
`formatters.client.ts` document this boundary. Feature 041 (I18N-003) followed exactly this pattern in
the now-localized list clients and `StatusBadge.tsx`.

**Alternatives considered**: Importing `t`/`formatCurrency` from `@/lib/i18n` (server) — rejected:
breaks the client bundle boundary and is inconsistent with prior i18n features.

## Decision 2 — Alert type label source

**Decision**: AlertDetailClient renders the Type field via `useAlertTypeLabel()` (catalog
`alert.types.*` with a humanized fallback), replacing the English-only `alertTypeLabel` from
`@/lib/alerts`.

**Rationale**: FR-003 requires alert types through the *localized* label map. `useAlertTypeLabel()`
already exists (client.tsx), returns the catalog Portuguese label when present and a humanized Title
Case fallback otherwise — never a raw key. `@/lib/alerts:alertTypeLabel` is an English-only map and
would leak English; it stays for any non-localized/server caller but the detail page switches off it.

**Alternatives considered**: Translating `@/lib/alerts` — rejected: it is a shared pure module also
used outside React; the localized path already exists as a hook.

## Decision 3 — Catalog key grouping

**Decision**: Add a `detail` section (shared detail-page chrome: back links, loading/not-found/error,
section headings, resolution UI, evidence, affected/linked entries, document image, related docs,
table column headers), an `analysis` section (the attachment-analysis dialog: title, section
headings, extracted-field labels, match-pill verbs, payment-reconciled badge, empty states), and a
`viewer` section (page-image viewer: unavailable placeholder, enlarge aria, alt templates). Reuse
existing keys where the concept already exists: `status.over/within/under/unknown`,
`table.period/date/description/category/vendor/unit/amount/type/total/number/issuer`, `button.close`,
`alert_status.*`, `severity.*`.

**Rationale**: Intent-revealing grouping matches the catalog's existing style (`page.*`, `dialog.*`,
`match.*`, `meta.*`). Reusing existing keys avoids duplication (Assumption A3). Interpolated strings
(e.g. "Página {label}", "Ampliar {alt}") are stored as templates and the component does the
substitution — consistent with how `notice.deeplink_not_found_*` and `list.entry_n` are handled
(prefix/suffix or `{n}`-style placeholders).

**Alternatives considered**: One flat section per file — rejected: the dialog/viewer chrome is reused
across call sites (entries view + alert detail), so a shared semantic grouping reads better and
prevents per-call-site duplication.

## Decision 4 — Interpolation style

**Decision**: For strings with a runtime value, store either (a) a template with a `{placeholder}` the
component replaces with `String.prototype.replace`, or (b) prefix/suffix keys the component composes
(matching `notice.deeplink_not_found_prefix`/`_suffix`). Use (a) for single-value cases (alt text,
page label, "this alert is resolved (…)"), (b) only where the existing catalog already established it.

**Rationale**: The I18N-001 catalog has no ICU message-format runtime; existing code uses simple
`{n}`-replace (`list.entry_n` = "Lançamento {n}") and prefix/suffix composition. Reusing those keeps
the mechanism uniform with zero new dependency.

## Decision 5 — Counts in headings

**Decision**: Headings like "Affected entries (N)" / "Linked entries (N)" / "Source attachments (N)"
render as `t("detail.<heading>") + " (" + n + ")"` — the parenthesized count stays a literal numeral
appended in the component (locale-neutral digits), not a pluralized catalog phrase.

**Rationale**: The count is a numeral, not translatable text; appending it keeps parity with the
current UI and avoids unnecessary plural-rule keys. The existing list pages already append raw counts
the same way.

## No open questions

There are no NEEDS CLARIFICATION markers. The foundation (#64) and prior i18n features fix every
mechanism; the only work is string extraction + key additions.
