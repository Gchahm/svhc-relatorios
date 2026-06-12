# Implementation Plan: Localize auth pages and dashboard shell to pt-BR (I18N-002)

**Branch**: `040-i18n-auth-shell-ptbr` | **Date**: 2026-06-12 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/040-i18n-auth-shell-ptbr/spec.md`

## Summary

Move every user-facing string in the auth pages (`sign-in`, `sign-up`) and the dashboard
shell (`dashboard/layout.tsx`, `UserMenu.tsx`, `SignOutButton.tsx`) into the existing
I18N-001 typed message catalog and render via the i18n layer (`useTranslation` for client
components, `t`/`getLocale` for server). Extend `CatalogShape` with the new `nav`, `auth`,
`app`, and `access` keys (in both `pt-BR` and `en`), establishing the canonical
fiscal/condominium glossary. Localize document titles (root `metadata.title` → pt-BR app
name; client auth pages set `document.title` via effect). Zero behavioral change; quality
gates and the catalog-completeness test pass.

## Technical Context

**Language/Version**: TypeScript 5 / React 19 / Next.js 15 (App Router)
**Primary Dependencies**: Existing only — the I18N-001 i18n layer (`@/lib/i18n`,
`@/lib/i18n/client`), shadcn/ui, lucide-react. **No new npm dependency.**
**Storage**: N/A — presentation-layer only; reads no data, writes nothing; no D1 schema,
no migration, no API shape change.
**Testing**: Node's built-in `node:test` via the existing `.test.mjs` pattern
(`src/lib/i18n/catalog.test.mjs`), run with `node --test`. Manual UI verification via the
`verify`/`ui-login` skills against local D1.
**Target Platform**: Cloudflare Workers / OpenNext (edge-safe; no Node-only APIs added).
**Project Type**: Web (single Next.js app).
**Performance Goals**: N/A — static string lookups; no runtime cost change.
**Constraints**: Must respect the i18n server/client import boundary (never import the
server barrel `@/lib/i18n` from a client component — it pulls in `getCloudflareContext`).
Client components use `@/lib/i18n/client`.
**Scale/Scope**: 5 component files + 1 catalog file + 1 test file; ~30 new catalog keys.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- **I. Type Safety & Schema Discipline**: PASS. New catalog keys are added to the typed
  `CatalogShape`, so the catalog stays type-complete and missing keys are compile errors.
  No `any`. No D1/Drizzle schema change, no migration, no auth-schema regeneration.
- **II. Cloudflare-Native Architecture**: PASS. No new bindings, no DB access. The
  server/client import boundary of the i18n layer (edge-safe) is preserved.
- **III. Quality Gates Before Commit**: PASS. `pnpm lint` + `pnpm format` will run; the
  spec explicitly requests catalog-completeness test coverage (Principle III's
  "tests when the spec requests them"), satisfied by extending `catalog.test.mjs`.
- **IV. Security & Auth by Default**: PASS. The auth flow, middleware, and role gate are
  untouched (FR-011); only rendered text moves. No secrets, no route changes.
- **V. Simplicity & Incremental Delivery**: PASS. Reuses the existing i18n primitives;
  adds no new abstraction. The work is additive catalog keys + string substitution.

No violations → Complexity Tracking left empty.

## Project Structure

### Documentation (this feature)

```text
specs/040-i18n-auth-shell-ptbr/
├── plan.md              # This file
├── spec.md              # Feature spec (+ Clarifications)
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output (catalog key model)
├── quickstart.md        # Phase 1 output (verify steps)
├── contracts/
│   └── catalog-keys.md  # Phase 1 output (the new catalog-key "contract")
├── checklists/
│   └── requirements.md  # spec quality checklist
└── tasks.md             # Phase 2 (speckit tasks)
```

### Source Code (repository root)

```text
src/
├── lib/i18n/
│   ├── catalog.ts            # EXTEND: CatalogShape + pt-BR + en (nav, auth, app, access)
│   └── catalog.test.mjs      # EXTEND: assert new keys present in both locales
└── app/
    ├── layout.tsx            # EDIT: metadata.title → app.title (pt-BR app name)
    ├── sign-in/page.tsx      # EDIT: useTranslation; document.title effect
    ├── sign-up/page.tsx      # EDIT: useTranslation; document.title effect
    └── dashboard/
        ├── layout.tsx        # EDIT: t() for nav labels + access-denied (server component)
        ├── UserMenu.tsx      # EDIT: useTranslation for sign-out label/loading
        └── SignOutButton.tsx # EDIT: useTranslation for label/loading/error fallback
```

**Structure Decision**: Single Next.js web app. All edits are within `src/app/` (the
in-scope surfaces) and `src/lib/i18n/` (the catalog + its test). No new directories.

## Phase 0 — Research

See [research.md](./research.md). Key decisions:
- Client-component document title via `useEffect` setting `document.title` (auth pages
  cannot export `metadata`); root layout keeps the static `metadata` with a localized title.
- `dashboard/layout.tsx` is a server (async) component → use `t()` from `@/lib/i18n`.
- `UserMenu`/`SignOutButton`/auth pages are client components → use `useTranslation()` from
  `@/lib/i18n/client`.
- New catalog sections: extend `nav` (reports, summary, comparison, vendors, units, fines,
  runs), extend `auth` (sign-up + helper links + idle/loading/error), add `app` (title) and
  `access` (denied heading/message).

## Phase 1 — Design & Contracts

- [data-model.md](./data-model.md): the catalog-key additions (the only "data").
- [contracts/catalog-keys.md](./contracts/catalog-keys.md): the exact new keys + pt-BR/en
  values (the glossary contract the test enforces).
- [quickstart.md](./quickstart.md): how to verify in the running app.

## Complexity Tracking

No constitution violations — section intentionally empty.
