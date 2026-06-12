# Tasks: Localize auth pages and dashboard shell to pt-BR (I18N-002)

**Feature Branch**: `040-i18n-auth-shell-ptbr`
**Spec**: [spec.md](./spec.md) | **Plan**: [plan.md](./plan.md) | **Contract**: [contracts/catalog-keys.md](./contracts/catalog-keys.md)

Presentation-layer only: extend the I18N-001 catalog and route in-scope strings through the
i18n layer. No D1 schema, no API, no Python.

## Phase 1: Setup

- [X] T001 Confirm branch `040-i18n-auth-shell-ptbr` is checked out and the working tree is clean; verify the i18n foundation exists at `src/lib/i18n/catalog.ts`, `src/lib/i18n/client.tsx`, `src/lib/i18n/index.ts`, and `src/lib/i18n/server.ts`.

## Phase 2: Foundational (blocks all user stories)

The catalog is the single source of truth every component reads from, so it must land first.

- [X] T002 Extend the typed `CatalogShape` in `src/lib/i18n/catalog.ts`: add the new `nav` keys (`reports`, `summary`, `comparison`, `vendors`, `units`, `fines`, `runs`), the new `auth` keys (`sign_in_email_placeholder`, `signing_in`, `unexpected_error`, `no_account_prompt`, `create_account_link`, `sign_up_title`, `sign_up_description`, `name_label`, `name_placeholder`, `confirm_password_label`, `sign_up_button`, `signing_up`, `sign_up_error`, `passwords_no_match`, `have_account_prompt`, `sign_in_link`, `signing_out`, `sign_out_error`), a new `app` section (`title`), and a new `access` section (`denied_title`, `denied_message`) — exactly per `contracts/catalog-keys.md`.
- [X] T003 Add the canonical `pt-BR` values for every new key in `src/lib/i18n/catalog.ts`, using the glossary values from `contracts/catalog-keys.md`.
- [X] T004 Add the matching `en` values for every new key in `src/lib/i18n/catalog.ts` (structural parity), per `contracts/catalog-keys.md`.
- [X] T005 Extend `src/lib/i18n/catalog.test.mjs` with targeted assertions that each new key resolves to a non-empty string in BOTH `pt-BR` and `en`; run `node --test src/lib/i18n/catalog.test.mjs` and confirm it passes.

**Checkpoint**: catalog type-checks (`pnpm lint`) and the completeness test passes — all stories can now consume keys.

## Phase 3: User Story 1 — Auth pages in pt-BR (Priority: P1)

**Goal**: `/sign-in` and `/sign-up` render every string from the catalog in pt-BR.
**Independent test**: load both pages logged out; trigger a failed sign-in and a sign-up password mismatch; all visible text + errors are catalog-backed pt-BR.

- [X] T006 [US1] In `src/app/sign-in/page.tsx`, import `useTranslation` from `@/lib/i18n/client`, get `const t = useTranslation()`, and replace every hardcoded user-facing string (card title, description, Email/Senha labels, email placeholder, submit idle/loading, the `setError` fallbacks, and the "Não tem conta? / Criar conta" link) with the keys mapped in `contracts/catalog-keys.md`. Keep all form state, handlers, and the auth-client call unchanged.
- [X] T007 [US1] In `src/app/sign-in/page.tsx`, set the document title from the catalog via a `useEffect` that assigns `document.title = t("app.title")` (no conversion to a server component).
- [X] T008 [US1] In `src/app/sign-up/page.tsx`, import `useTranslation`, replace every hardcoded user-facing string (card title, description, Nome/Email/Senha/Confirmar senha labels, name + email placeholders, submit idle/loading, the password-mismatch and error fallbacks, and the "Já tem conta? / Entrar" link) per `contracts/catalog-keys.md`, leaving handlers/auth call unchanged.
- [X] T009 [US1] In `src/app/sign-up/page.tsx`, set the document title from the catalog via a `useEffect` (`document.title = t("app.title")`).

**Checkpoint**: auth pages fully catalog-backed; sign-in/sign-up flows behave identically.

## Phase 4: User Story 2 — Dashboard shell in pt-BR (Priority: P1)

**Goal**: nav links, user menu, sign-out, and access-denied gate render pt-BR from the catalog.
**Independent test**: sign in as an approved member → every nav label is the glossary term; user-menu sign-out shows pt-BR idle/loading; an unapproved role sees the pt-BR access-denied screen.

- [X] T010 [US2] In `src/app/dashboard/layout.tsx` (async server component), import `t` from `@/lib/i18n`, and replace each `NavLink` label (Reports, Entries, Summary, Comparison, Vendors, Documents, Units, Fines, Alerts, Runs) with the corresponding `t("nav.*")` call per `contracts/catalog-keys.md`. Leave icons, hrefs, and structure unchanged.
- [X] T011 [US2] In `src/app/dashboard/layout.tsx`, replace the access-denied heading and explanatory paragraph with `t("access.denied_title")` and `t("access.denied_message")`.
- [X] T012 [US2] In `src/app/dashboard/UserMenu.tsx`, import `useTranslation` from `@/lib/i18n/client` and replace the sign-out menu item label and its loading state with `t("auth.sign_out")` / `t("auth.signing_out")`.
- [X] T013 [US2] In `src/app/dashboard/SignOutButton.tsx`, import `useTranslation` and replace the button label, loading state, and the error fallback string with `t("auth.sign_out")` / `t("auth.signing_out")` / `t("auth.sign_out_error")` (keep the geolocation + sign-out logic unchanged).

**Checkpoint**: the shell renders pt-BR throughout from the catalog.

## Phase 5: User Story 3 — Localized titles (Priority: P2)

**Goal**: document/tab titles reflect the pt-BR app name.
**Independent test**: inspect the document title on `/sign-in`, `/sign-up`, and a dashboard route — each is the pt-BR app title.

- [X] T014 [US3] In `src/app/layout.tsx`, change the static `metadata.title` from the hardcoded `"SVHC Fiscal"` literal to the catalog value via `t("app.title")` (server `t` from `@/lib/i18n`), keeping `metadata.description` and the `LocaleProvider` wiring intact. (The auth-page `document.title` effects from T007/T009 cover the client pages.)

**Checkpoint**: all in-scope surfaces have pt-BR titles.

## Phase 6: Polish & Cross-Cutting

- [X] T015 Grep the five in-scope component files for residual hardcoded user-facing string literals (excluding icons, hrefs, machine ids, and the brand link text) and confirm none remain that should be catalog-backed.
- [X] T016 Run `node --test src/lib/i18n/catalog.test.mjs`, `pnpm lint`, and `pnpm format` (write) / `pnpm format --check`; fix any issues until all pass.
- [X] T017 Manually verify in the running app against local data per `quickstart.md` (use the `ui-login`/`verify` skills): pt-BR throughout, failed sign-in error pt-BR, sign-up mismatch pt-BR, nav glossary terms, access-denied screen, and that a correct credential still signs in.

## Dependencies

- Phase 2 (T002–T005) blocks all of Phase 3/4/5 (components read the keys).
- US1, US2, US3 are independent of each other once the catalog exists; T014 (US3) only needs T002–T004 (the `app.title` key).
- Phase 6 runs after the story phases.

## Parallel opportunities

- T006/T007 (sign-in) and T008/T009 (sign-up) touch different files → parallelizable after Phase 2.
- T010/T011 (layout), T012 (UserMenu), T013 (SignOutButton) touch different files → parallelizable after Phase 2.

## Implementation strategy (MVP first)

MVP = Phase 2 + US1 (auth pages catalog-backed pt-BR) — the highest-visibility surface.
Then US2 (shell) and US3 (titles), then polish/verify.
