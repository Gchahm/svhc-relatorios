# Phase 0 Research: I18N-002 auth + shell localization

## Decision 1 — Translation API per component kind

**Decision**: Server (async) components use `t(key)` and `getLocale()` from the server
barrel `@/lib/i18n`. Client components (`"use client"`) use `useTranslation()` /
`useLocale()` from `@/lib/i18n/client`.

**Rationale**: The server barrel `@/lib/i18n` imports `./server` which calls
`getCloudflareContext()`; importing it from a client component drags server-only code into
the client bundle (the barrel's own NOTE warns against this). `dashboard/layout.tsx` is an
`async` server component, so `t()` is correct there. `sign-in`, `sign-up`, `UserMenu`,
`SignOutButton` are all `"use client"`, so the hook is correct there. `LocaleProvider`
already wraps the app in the root layout, so `useTranslation()` has its context.

**Alternatives considered**: Passing translated strings down as props from a server
component — rejected as more invasive and unnecessary since `LocaleProvider` is in place.

## Decision 2 — Document title in client auth pages

**Decision**: Auth pages set `document.title` from a catalog `app.title` key inside a
`useEffect`. The root layout keeps its static `export const metadata` but its `title`
becomes the localized `app.title`.

**Rationale**: `sign-in`/`sign-up` are client components and cannot export Next.js
`metadata`. A one-line `useEffect(() => { document.title = t("app.title"); }, [t])` is the
minimal, behavior-safe way to localize the tab title without converting them to server
components (which would risk the better-auth client hooks and the existing form state).
Dashboard pages inherit the root layout title (acceptable per spec US3 — pt-BR app title).

**Alternatives considered**: Converting auth pages to server components with a client
sub-form — rejected (behavioral risk, larger diff, no user benefit). Adding per-page
`metadata` objects — impossible in client components.

## Decision 3 — Catalog extensions (glossary)

**Decision**: Extend the existing sections and add two small sections, keeping both locales
in sync:
- `nav.*`: reuse `entries`, `documents`, `alerts`; add `reports`, `summary`, `comparison`,
  `vendors`, `units`, `fines`, `runs`.
- `auth.*`: reuse `sign_in_title`, `email_label`, `password_label`, `sign_in_button`,
  `sign_in_error`, `sign_out`; add the rest needed by the two pages (descriptions, the
  loading states, the sign-up title/description/fields, the helper-link prompts/actions,
  the password-mismatch and generic-error fallbacks, name field + placeholders).
- `app.title`: the product/brand title ("SVHC Fiscal" in both locales).
- `access.denied_title`, `access.denied_message`: the role-gate screen.

**Rationale**: Reusing existing keys avoids duplication and honors the "glossary" goal — the
nav terms become the canonical vocabulary. The `pt-BR` values use the natural fiscal/
condominium terms decided in spec A5. `en` mirrors the prior English nav labels so the
existing structural completeness test stays green.

**Glossary (pt-BR canonical / en)**:
| key | pt-BR | en |
|-----|-------|----|
| nav.reports | Prestação de contas | Reports |
| nav.summary | Resumo | Summary |
| nav.comparison | Comparação | Comparison |
| nav.vendors | Fornecedores | Vendors |
| nav.units | Unidades | Units |
| nav.fines | Multas | Fines |
| nav.runs | Execuções | Runs |
| nav.entries (existing) | Lançamentos | Entries |
| nav.documents (existing) | Documentos | Documents |
| nav.alerts (existing) | Alertas | Alerts |

## Decision 4 — Test strategy

**Decision**: Extend `src/lib/i18n/catalog.test.mjs`. Add explicit assertions that each new
key resolves to a non-empty string in BOTH `pt-BR` and `en`. The existing structural-parity
test (every pt-BR leaf present in en and vice-versa) already covers completeness; add
targeted assertions for the new glossary keys so a regression on a specific term is caught.

**Rationale**: Principle III: tests added because the spec requests catalog-completeness
coverage (FR-010, SC-003). Node's built-in `node:test` requires no new dependency.

## Edge-safety

No Node-only APIs introduced. `document.title` is a browser API used only inside a client
`useEffect` (runs in the browser, never on the edge). All catalog data is static.
