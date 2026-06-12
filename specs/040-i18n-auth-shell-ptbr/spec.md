# Feature Specification: Localize auth pages and dashboard shell to pt-BR (I18N-002)

**Feature Branch**: `040-i18n-auth-shell-ptbr`
**Created**: 2026-06-12
**Status**: Draft
**Input**: User description: "Localize auth pages and dashboard shell to pt-BR using the I18N-001 catalog: sign-in, sign-up, nav, user menu, sign-out, page metadata titles; establish the pt-BR fiscal/condominium glossary"

## Context

The I18N-001 foundation (issue #64, merged) shipped a typed message catalog
(`src/lib/i18n/catalog.ts`), client/server translation helpers (`useTranslation`,
`t`, `getLocale`), a `LocaleProvider` already wired into the root layout, and a
catalog-completeness test (`catalog.test.mjs`). pt-BR is the rendered default.

The first surfaces a user ever sees — the sign-in and sign-up pages and the
dashboard shell (top navigation, page chrome, user menu, sign-out, the
access-denied gate) — still hold hardcoded strings. The auth pages are partly
hardcoded-Portuguese; the dashboard shell is hardcoded English. None of these
strings flow through the catalog, so the locale layer is not the source of truth
for them and the shell does not render consistent pt-BR.

This feature moves every user-facing string in those surfaces into the catalog
and renders it through the i18n layer, and establishes the canonical pt-BR
fiscal/condominium glossary that the follow-up issues (I18N-003 list pages,
I18N-004 detail pages/dialogs) reuse.

## Clarifications

### Session 2026-06-12

Running unattended (speckit `full` one-shot), the following decision points were
resolved with reasonable defaults rather than interactive questions; each is also
captured in the Assumptions section.

- Q: How should client-component auth pages set their document title (they cannot
  export Next.js `metadata`)? → A: A small `useEffect` sets `document.title` from a
  catalog app-title key; no conversion to server components (avoids behavioral risk).
- Q: The auth pages already show hardcoded Portuguese — is the work just to move
  those literals into the catalog, or also to retranslate? → A: Move every literal
  to catalog keys (the requirement); refine wording to the canonical glossary, keep
  the pages Portuguese.
- Q: Should this feature add a locale switcher / cookie persistence? → A: No — out of
  scope; `getLocale` keeps returning pt-BR. Only render the active locale and keep
  the `en` catalog structurally complete.
- Q: Is "SVHC Fiscal" localized? → A: No — treated as a product/brand proper name;
  identical in both locales, surfaced via an `app.title` catalog key for metadata.
- Q: Are `src/app/page.tsx` and `src/app/dashboard/page.tsx` in scope? → A: They are
  pure `redirect()` server components with no user-facing text; no string change
  needed (documented, not silently skipped).

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Sign in and sign up entirely in pt-BR (Priority: P1)

A SVHC member arrives at the app with no stored locale preference. The sign-in
page (and the sign-up page they can navigate to) presents every label,
placeholder, button, helper link, and error message in natural Brazilian
Portuguese, sourced from the message catalog rather than hardcoded.

**Why this priority**: The auth pages are the literal first screen every user
sees; an unauthenticated user cannot reach anything else. Inconsistent or
hardcoded text here is the most visible localization gap.

**Independent Test**: Visit `/sign-in` and `/sign-up` with no locale cookie;
confirm all visible text is pt-BR. Trigger a failed sign-in (wrong password) and
a password-mismatch on sign-up; confirm the error messages render in pt-BR from
the catalog. Verify no English string appears.

**Acceptance Scenarios**:

1. **Given** a visitor with no stored locale preference, **When** they open
   `/sign-in`, **Then** the title, description, the Email and Senha labels, the
   email placeholder, the submit button (idle and loading), and the "create
   account" helper link all render in pt-BR.
2. **Given** the sign-in form, **When** the credentials are rejected, **Then** a
   pt-BR error message is shown (falling back to a catalog default when the auth
   service returns none).
3. **Given** `/sign-up`, **When** the two password fields differ on submit,
   **Then** a pt-BR "passwords do not match" message appears.
4. **Given** any catalog-backed auth string, **When** the catalog is inspected,
   **Then** the rendered text comes from a catalog key (no hardcoded literal in
   the component for that string).

### User Story 2 - Dashboard shell navigation and chrome in pt-BR (Priority: P1)

An authenticated member lands on the dashboard. The top navigation links
(Reports, Entries, Summary, Comparison, Vendors, Documents, Units, Fines,
Alerts, Runs), the user menu (sign-out action) and the access-denied gate all
render in pt-BR using the fiscal/condominium glossary.

**Why this priority**: The shell wraps every dashboard page; its nav labels are
the persistent vocabulary of the whole app and seed the glossary the rest of the
track depends on.

**Independent Test**: Sign in as an approved member; confirm every nav item, the
user-menu sign-out item (idle and loading), and the access-denied screen (when
signed in as an unapproved user) render in pt-BR from the catalog.

**Acceptance Scenarios**:

1. **Given** an authenticated member on `/dashboard`, **When** the shell renders,
   **Then** every top-nav link label is the pt-BR glossary term.
2. **Given** the user menu is open, **When** sign-out is invoked, **Then** the
   menu item shows a pt-BR "signing out…" state and a pt-BR "sign out" label.
3. **Given** a signed-in user whose role is not approved, **When** the dashboard
   layout renders, **Then** the access-denied heading, explanation, and the
   sign-out button render in pt-BR.

### User Story 3 - Localized page/document titles (Priority: P2)

The browser tab title (document `<title>`) reflects the app in pt-BR for the
auth pages and the dashboard shell, instead of a generic or English title.

**Why this priority**: Lower visibility than on-screen text, but part of the
"renders in pt-BR by default" acceptance and trivial once the catalog is in use.

**Independent Test**: Load `/sign-in`, `/sign-up`, and a dashboard route; inspect
the document title; confirm it is a pt-BR app title from the catalog.

**Acceptance Scenarios**:

1. **Given** any in-scope page, **When** it loads, **Then** its document title is
   a pt-BR string derived from the catalog (not hardcoded English).

### Edge Cases

- **Auth-service error**: better-auth returns English-only `error.message` strings,
  so the auth handlers map the known `error.code` to a catalog key (rather than
  surfacing the raw message): `INVALID_EMAIL_OR_PASSWORD` → `auth.invalid_credentials`,
  `USER_ALREADY_EXISTS_USE_ANOTHER_EMAIL` → `auth.email_in_use`; any other code falls
  back to the catalog generic ("Falha ao entrar." / "Falha ao criar conta."). Every
  user-facing auth error therefore renders in the active locale.
- **Unexpected exception during auth**: Network/throw paths show a catalog-backed
  pt-BR generic error ("Erro inesperado. Tente novamente.").
- **`en` locale selected** (foundation supports it): the same surfaces render the
  English catalog values, falling back to pt-BR for any key missing in `en`. This
  feature keeps `en` in sync for all keys it adds.
- **Glossary collision**: Nav already-existing catalog keys (`nav.entries`,
  `nav.documents`, `nav.alerts`) must be reused — not duplicated — and the
  newly-added nav terms must not conflict.
- **No behavioral change**: routes, middleware, the auth flow, and role-gating
  logic are untouched; only rendered text changes.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: Every user-facing string in `src/app/sign-in/page.tsx` MUST render
  from a catalog key via the i18n layer: card title, card description, Email
  label, Senha label, email placeholder, submit button idle/loading text, the
  inline error fallbacks, and the "Não tem conta? / Criar conta" helper link.
- **FR-002**: Every user-facing string in `src/app/sign-up/page.tsx` MUST render
  from a catalog key: card title, description, Nome/Email/Senha/Confirmar senha
  labels, name and email placeholders, submit button idle/loading text, the
  password-mismatch and error fallbacks, and the "Já tem conta? / Entrar" helper
  link.
- **FR-003**: Every nav link label in `src/app/dashboard/layout.tsx` (Reports,
  Entries, Summary, Comparison, Vendors, Documents, Units, Fines, Alerts, Runs)
  MUST render from a catalog key, reusing existing `nav.*` keys where present and
  adding new ones for the rest.
- **FR-004**: The access-denied block in `src/app/dashboard/layout.tsx` (heading
  and explanatory text) MUST render from catalog keys in pt-BR.
- **FR-005**: The user menu (`src/app/dashboard/UserMenu.tsx`) sign-out item MUST
  render its label and loading state from catalog keys.
- **FR-006**: The standalone sign-out button (`src/app/dashboard/SignOutButton.tsx`)
  MUST render its label, loading state, and error fallback from catalog keys.
- **FR-007**: Document titles for the in-scope surfaces MUST be pt-BR strings
  derived from the catalog. The root layout's `metadata.title` MUST use the pt-BR
  app title; auth pages (client components) MUST set their document title from the
  catalog without breaking the existing `"use client"` boundary.
- **FR-008**: All new catalog keys MUST be added to the typed `CatalogShape` and
  to BOTH the `pt-BR` (canonical) and `en` locale objects, keeping the catalog
  type-complete and the `en` fallback in sync.
- **FR-009**: The pt-BR values MUST use natural Brazilian fiscal/condominium
  vocabulary, establishing a reusable glossary (e.g. "Lançamentos" for entries,
  "Alertas", "Prestação de contas" for accountability reports, "Fornecedores",
  "Unidades", "Multas", "Resumo", "Comparação", "Execuções" for runs).
- **FR-010**: The catalog-completeness test MUST cover the new keys (every key in
  `pt-BR` present, and the `en` catalog kept structurally complete so the
  existing test continues to pass).
- **FR-011**: No behavioral change — auth flows, routes, middleware, and the
  role-gating logic remain byte-for-byte equivalent; only the rendered text
  strings move into the catalog.
- **FR-012**: Client components that need translation MUST use the existing
  `useTranslation`/`useLocale` hooks from `@/lib/i18n/client`; server components
  MUST use `t`/`getLocale` from `@/lib/i18n` (the server barrel), preserving the
  established server/client import-boundary rule (never import the server barrel
  from a client component).

### Key Entities *(include if feature involves data)*

- **Message catalog** (`src/lib/i18n/catalog.ts`): the typed nested dictionary.
  This feature extends its `nav`, `auth`, `page` (and adds an `app`/`access`
  grouping as needed) sections with the new keys, in both locales. No D1 schema,
  no API shape, no Python touched.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Visiting `/sign-in`, `/sign-up`, and `/dashboard` with no stored
  locale preference shows 100% pt-BR text in the in-scope surfaces — zero English
  strings remain in the rendered auth pages and shell.
- **SC-002**: Every in-scope user-facing string resolves through a catalog key —
  a reviewer can grep the in-scope component files and find no hardcoded
  user-facing text literal that should be translated (icons, hrefs, and machine
  ids excepted).
- **SC-003**: `pnpm lint`, `pnpm format --check`, and the i18n catalog-completeness
  test (and any other existing tests) all pass.
- **SC-004**: The auth flow behaves identically — a correct credential still signs
  in and redirects to `/dashboard`; a wrong credential still shows an error (now
  pt-BR); the role gate still blocks unapproved users — verified in the running
  app against local data.
- **SC-005**: The glossary terms are documented in the catalog and reused by the
  nav so I18N-003/004 can adopt them without re-deciding vocabulary.

## Assumptions

- **A1 (no locale switcher in scope)**: The foundation defaults to pt-BR and has
  no persisted switcher yet (`getLocale` always returns `pt-BR`). This feature
  does not add a switcher; it just ensures the in-scope surfaces render the active
  locale. Keeping `en` in sync is for catalog correctness/future use only.
- **A2 (auth-page Portuguese is not "done")**: The sign-in/sign-up pages are
  already hardcoded in Portuguese, but per the issue they must be *catalog-backed*.
  This feature replaces those hardcoded literals with catalog lookups; the visible
  pt-BR text may be refined to the canonical glossary but the page stays Portuguese.
- **A3 (client-component document title)**: The auth pages are client components,
  so they cannot export Next.js `metadata`. We set the document title via a small
  effect using the catalog value. The root layout's static `metadata.title`
  becomes the pt-BR app title. We will not convert auth pages to server components
  (behavioral-risk).
- **A4 (brand string)**: "SVHC Fiscal" is treated as a product/brand name and may
  remain a literal in the header link, but the app-title metadata is localized.
  The app-title catalog value reads "SVHC Fiscal" (a proper name) in both locales.
- **A5 (glossary choices)**: Reports → "Prestação de contas", Summary → "Resumo",
  Comparison → "Comparação", Vendors → "Fornecedores", Units → "Unidades", Fines →
  "Multas", Runs → "Execuções", Entries → "Lançamentos" (existing), Documents →
  "Documentos" (existing), Alerts → "Alertas" (existing). These are the canonical
  glossary terms for the track.
- **A6 (en values)**: New `en` values mirror the current English nav labels and
  natural English auth strings, so the existing completeness test (which checks
  structural parity) keeps passing.
- **A7 (scope boundary)**: `src/app/page.tsx` and `src/app/dashboard/page.tsx` are
  pure `redirect()` server components with no user-facing text; they are in the
  issue's file list but require no string changes (documented, not skipped).
