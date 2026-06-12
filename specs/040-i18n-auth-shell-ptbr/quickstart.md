# Quickstart / Verification: I18N-002

## Build & gate checks

```bash
cd /home/agent/workspace/svhc-relatorios
node --test src/lib/i18n/catalog.test.mjs   # catalog completeness + new-key assertions
pnpm lint
pnpm format --check
```

## Manual UI verification (running app, local D1)

Use the `ui-login` skill to start the dev server and log in (handles the container
port/origin and ensures a test admin user). Then:

1. **/sign-in (logged out)**: confirm title, description, Email + Senha labels, email
   placeholder, the "Entrar"/"Entrando..." button, and the "Não tem conta? Criar conta"
   link are all pt-BR. Tab title shows the pt-BR app name.
2. **Failed sign-in**: submit a wrong password → pt-BR error appears.
3. **/sign-up**: confirm Nome/Email/Senha/Confirmar senha labels, placeholders, button, and
   "Já tem conta? Entrar" link are pt-BR. Submit mismatched passwords → pt-BR mismatch error.
4. **/dashboard (logged in as approved member)**: every top-nav link reads the pt-BR
   glossary term (Prestação de contas, Lançamentos, Resumo, Comparação, Fornecedores,
   Documentos, Unidades, Multas, Alertas, Execuções). Open the user menu → "Sair"; invoke
   it → "Saindo..." state.
5. **Access-denied** (a user without an approved role): heading "Acesso negado", the pt-BR
   explanation, and the "Sair" button.

## Behavioral non-regression

- A correct credential still signs in and redirects to `/dashboard`.
- A wrong credential still shows an error (now pt-BR).
- The role gate still blocks unapproved users (now pt-BR copy).
- Routes, middleware, and the auth client calls are byte-for-byte unchanged.
