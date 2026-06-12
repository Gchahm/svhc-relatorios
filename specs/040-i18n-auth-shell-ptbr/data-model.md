# Phase 1 Data Model: I18N-002

This feature touches no persisted data (no D1 schema, no API shape). The only "model" is
the typed message catalog (`CatalogShape` in `src/lib/i18n/catalog.ts`). Below is the
delta: existing keys reused, and new keys added (each present in `pt-BR` canonical and `en`).

## Entity: CatalogShape (extended)

### `nav` (extend existing)

Existing: `home`, `entries`, `documents`, `alerts`, `dashboard`, `settings`.
Add: `reports`, `summary`, `comparison`, `vendors`, `units`, `fines`, `runs`.

### `auth` (extend existing)

Existing: `sign_in_title`, `sign_in_description`, `email_label`, `password_label`,
`sign_in_button`, `sign_in_error`, `invalid_credentials`, `session_expired`, `sign_out`.

Add:
- `sign_in_email_placeholder` — email input placeholder
- `signing_in` — submit button loading state
- `unexpected_error` — generic catch-all error fallback
- `no_account_prompt` — "Não tem conta?"
- `create_account_link` — "Criar conta" (link to /sign-up)
- `sign_up_title` — sign-up card title
- `sign_up_description` — sign-up card description
- `name_label` — name field label
- `name_placeholder` — name field placeholder
- `confirm_password_label` — confirm-password field label
- `sign_up_button` — sign-up submit (idle)
- `signing_up` — sign-up submit loading state
- `sign_up_error` — sign-up generic failure fallback
- `passwords_no_match` — password-mismatch validation message
- `have_account_prompt` — "Já tem conta?"
- `sign_in_link` — "Entrar" (link to /sign-in)
- `signing_out` — sign-out loading state
- `sign_out_error` — sign-out failure fallback

### `app` (new section)

- `title` — product/brand title (proper name; identical in both locales: "SVHC Fiscal")

### `access` (new section)

- `denied_title` — access-denied heading
- `denied_message` — access-denied explanation

## Validation rules

- Every new key MUST exist in BOTH `pt-BR` and `en` (structural parity — enforced by the
  existing completeness test) and resolve to a non-empty string (enforced by new targeted
  assertions).
- `CatalogShape` (the TypeScript type) MUST list every new key, so a missing key in either
  locale object is a compile error (`tsc` / `pnpm lint`).

## State transitions

None — static dictionary.
