# Research: Localize the dashboard list pages to pt-BR

## R1 — Translation lookup API (client vs server)

**Decision**: Client list components use the `useTranslation()` hook from `@/lib/i18n/client` (returns `t(key)`); the `page.tsx` server components use `t(key)` from `@/lib/i18n`.

**Rationale**: This is exactly the split established by I18N-001/002. The barrel `@/lib/i18n` pulls in `./server` (`getCloudflareContext`), so it must never be imported from a client component — `client.tsx` is the client-safe entry. The `LocaleProvider` is already mounted in `src/app/layout.tsx`, so every dashboard client has locale context in scope.

**Alternatives considered**: Passing `t` down as props (rejected — unnecessary plumbing; the hook + provider already exist). A new context (rejected — duplicates the shipped one).

## R2 — Shared formatters from a client component

**Decision**: Client components import `formatCurrency`/`formatDate`/`formatPercent`/`formatNumber` from `@/lib/i18n/formatters` and pass the active locale explicitly via `useLocale()` (e.g. `formatCurrency(value, locale)`).

**Rationale**: `formatters.ts` defaults its locale via `getLocale()` (server-only `getCloudflareContext`). Each formatter already accepts an optional `locale` second/last argument. Passing `useLocale()` keeps the formatter shared and the bundle client-safe. Importing `@/lib/i18n/formatters` directly (not the barrel) is safe at module level only if it does not transitively eval server code at import — verify during implementation; if the import path drags server code, re-export the formatters from `client.tsx` or a client-safe module. (Note: `formatters.ts` imports `getLocale` from `./server` at top-level. We must confirm Next/OpenNext tree-shakes this for the client; the safe path is to expose a thin client-safe formatter wrapper if needed — see R6.)

**Alternatives considered**: Reimplementing Intl inline (rejected — that is exactly the per-file helper the issue says to delete). Keeping `toLocaleString("pt-BR", …)` (rejected — not locale-aware, not the shared formatter).

## R3 — Plural mechanism

**Decision**: Add a `count` catalog section with `<noun>_one` / `<noun>_other` string pairs, plus a tiny pure helper that selects the form by `n === 1`. The caller renders `${formatNumber-or-raw n} ${plural(...)}`.

**Rationale**: I18N-001 ships no ICU. The count nouns on these pages (lançamentos, alertas, documentos, fornecedores, unidades, multas, execuções, relatórios) follow the simple pt-BR rule "1 → singular, else plural", so a two-key select is sufficient and testable. Keeps zero new dependencies (constitution: simplicity).

**Alternatives considered**: `Intl.PluralRules` (works but still needs catalog forms; the two-key select is simpler and the rule is trivial here). English-suffix concatenation (rejected by FR-005).

## R4 — Alert type & severity labels

**Decision**: Alert type → `getAlertTypeLabel(type)` (server) / `t(\`alert.types.${type}\`)` semantics; severity (critical/warning/info) → a localized `badge`/`severity` catalog section. The English `alertTypeLabel()` from `@/lib/alerts` must not be rendered.

**Rationale**: FR-004 + feature 038. `getAlertTypeLabel` already exists in the barrel for server use. For the client `AlertsClient`, expose/Use the same `alert.types.*` keys via `useTranslation()` (the key is `alert.types.<type>`). A fallback to a humanized label (never raw snake_case) is required for any type not in the map.

**Alternatives considered**: Keeping `@/lib/alerts.alertTypeLabel` (rejected — English, FR-004).

## R5 — Document reconciliation status labels (over/within/under/unknown)

**Decision**: Add a `status` (or `documents.status`) catalog section with `over`/`within`/`under`/`unknown` labels; `StatusBadge.tsx` and `DocumentsClient` read them via `useTranslation()`. The status *computation* stays in `src/lib/documents.ts` (feature 036) — only the label text is localized.

**Rationale**: FR-001 + scope. `src/lib/documents.ts` holds the status math (shared with Python tolerance) — we localize the presentation, not the logic, to avoid touching the reconciliation contract.

## R6 — Client-safe formatter import (risk mitigation)

**Decision**: At implementation, first try importing the formatters directly from `@/lib/i18n/formatters` in a client component and building. If the client build fails or warns about server-only code (`getCloudflareContext`), add a client-safe re-export (a `"use client"`-free pure module, or re-export from `client.tsx`) that the list pages import instead — without changing the formatter signatures. Always pass an explicit `locale`, so `getLocale()` is never reached on the client.

**Rationale**: The formatters' only server dependency is the *default* `getLocale()` path; passing `locale` explicitly avoids calling it. The remaining risk is the top-level `import { getLocale } from "./server"` being included in the client bundle. Tree-shaking usually drops the unused symbol, but we de-risk with a verified build (`pnpm build` or the dev server) during implementation.

## R7 — Already-Portuguese pages

**Decision**: Pages already containing hand-written Portuguese (reports, comparison, scrape-runs, fines) still get every chrome literal moved into the catalog, preserving/normalizing the pt-BR wording to the I18N-002 glossary.

**Rationale**: FR-001/SC-002 require "no hardcoded chrome string remains in the listed files," and centralizing the glossary is the point of the feature.

## R8 — Out of scope

Detail pages, dialogs (`AttachmentAnalysisDetailDialog`), and standalone notices beyond the in-file deep-link notice are I18N-004 (#67). This feature touches list surfaces, their `page.tsx` titles, and `src/components/filters/*` only. The deep-link notice text that lives *inside* `EntriesClient.tsx` is in-scope (it is in a listed file).
