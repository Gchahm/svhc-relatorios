# Contract: Catalog keys (I18N-002)

The "contract" for this presentation-layer feature is the set of catalog keys and their
canonical values. The catalog-completeness test enforces structural parity; the component
edits consume exactly these keys.

## nav (additions)

| key | pt-BR | en |
|-----|-------|----|
| nav.reports | Prestação de contas | Reports |
| nav.summary | Resumo | Summary |
| nav.comparison | Comparação | Comparison |
| nav.vendors | Fornecedores | Vendors |
| nav.units | Unidades | Units |
| nav.fines | Multas | Fines |
| nav.runs | Execuções | Runs |

Reused (no change): nav.entries=Lançamentos, nav.documents=Documentos, nav.alerts=Alertas.

## auth (additions)

| key | pt-BR | en |
|-----|-------|----|
| auth.sign_in_email_placeholder | seu@email.com | you@email.com |
| auth.signing_in | Entrando... | Signing in... |
| auth.unexpected_error | Erro inesperado. Tente novamente. | Unexpected error. Please try again. |
| auth.no_account_prompt | Não tem conta? | Don't have an account? |
| auth.create_account_link | Criar conta | Create account |
| auth.sign_up_title | Criar conta | Create account |
| auth.sign_up_description | Preencha os dados abaixo para se registrar. | Fill in the details below to register. |
| auth.name_label | Nome | Name |
| auth.name_placeholder | Seu nome | Your name |
| auth.confirm_password_label | Confirmar senha | Confirm password |
| auth.sign_up_button | Criar conta | Create account |
| auth.signing_up | Criando conta... | Creating account... |
| auth.sign_up_error | Falha ao criar conta. | Failed to create account. |
| auth.email_in_use | Este email já está em uso. Use outro email. | This email is already in use. Use another email. |
| auth.passwords_no_match | As senhas não coincidem. | Passwords do not match. |
| auth.have_account_prompt | Já tem conta? | Already have an account? |
| auth.sign_in_link | Entrar | Sign in |
| auth.signing_out | Saindo... | Signing out... |
| auth.sign_out_error | Falha ao sair. Tente novamente. | Sign out failed. Please try again. |

Reused (existing): auth.sign_in_title (will be used as page title — currently "Entrar" /
"Sign In"), auth.email_label, auth.password_label, auth.sign_in_button, auth.sign_in_error
(used as the failed sign-in fallback "Falha ao entrar."), auth.invalid_credentials (mapped
from the better-auth `INVALID_EMAIL_OR_PASSWORD` code on a failed sign-in), auth.sign_out.

**Error-code mapping**: better-auth returns English-only `error.message` strings, so the
auth handlers map the known `error.code` to a catalog key instead of surfacing the raw
message — `INVALID_EMAIL_OR_PASSWORD` → `auth.invalid_credentials`,
`USER_ALREADY_EXISTS_USE_ANOTHER_EMAIL` → `auth.email_in_use`; any other code falls back to
`auth.sign_in_error` / `auth.sign_up_error`. This keeps every user-facing auth error in the
active locale.

Note: existing `auth.sign_in_description` = "Acesse sua conta para continuar"; the sign-in
page currently shows "Entre com seu email e senha." — we reuse the catalog value (the page
becomes catalog-backed; the visible wording aligns to the canonical catalog text).

## app (new)

| key | pt-BR | en |
|-----|-------|----|
| app.title | SVHC Fiscal | SVHC Fiscal |

## access (new)

| key | pt-BR | en |
|-----|-------|----|
| access.denied_title | Acesso negado | Access Denied |
| access.denied_message | Sua conta está aguardando aprovação. Entre em contato com um administrador para obter acesso. | Your account is pending approval. Contact an administrator to get access. |

## Consumption map

| Component | Keys used |
|-----------|-----------|
| src/app/layout.tsx | app.title (metadata) |
| src/app/sign-in/page.tsx | app.title, auth.sign_in_title, auth.sign_in_description, auth.email_label, auth.password_label, auth.sign_in_email_placeholder, auth.sign_in_button, auth.signing_in, auth.sign_in_error, auth.unexpected_error, auth.no_account_prompt, auth.create_account_link |
| src/app/sign-up/page.tsx | app.title, auth.sign_up_title, auth.sign_up_description, auth.name_label, auth.name_placeholder, auth.email_label, auth.sign_in_email_placeholder, auth.password_label, auth.confirm_password_label, auth.sign_up_button, auth.signing_up, auth.sign_up_error, auth.passwords_no_match, auth.unexpected_error, auth.have_account_prompt, auth.sign_in_link |
| src/app/dashboard/layout.tsx | nav.reports, nav.entries, nav.summary, nav.comparison, nav.vendors, nav.documents, nav.units, nav.fines, nav.alerts, nav.runs, access.denied_title, access.denied_message |
| src/app/dashboard/UserMenu.tsx | auth.sign_out, auth.signing_out |
| src/app/dashboard/SignOutButton.tsx | auth.sign_out, auth.signing_out, auth.sign_out_error |
