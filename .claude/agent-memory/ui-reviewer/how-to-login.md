---
name: how-to-login
description: How to authenticate into the svhc-relatorios dashboard (better-auth) before a UI review
---

The dashboard (`/dashboard/*`) is gated by **better-auth**. The simplest reliable path is to invoke
the repo's **`ui-login` skill** (Skill tool) with the target path — it does everything below,
idempotently, and lands the MCP browser on the page in the session I then review in. Use this first;
the steps are recorded here so I can recover if the skill is ever absent.

**Local throwaway creds** (local Miniflare only — never production):
`reviewer@svhc.local` / `Reviewer-2026!` (prefer `TEST_USER_EMAIL` / `TEST_USER_PASSWORD` from the
environment if set).

What `ui-login` handles (and what to do manually if needed):

1. **Dev server**: on `:3000` inside the container (external `:3001` forwards in). `307`/`200` = up
   (307 = redirect to `/sign-in`). Don't start a second `next dev`.
2. **Trusted origin** (the #1 cause of a 403 on sign-in): the MCP browser's origin
   `http://localhost:3000` must be in `BETTER_AUTH_TRUSTED_ORIGINS` in `.dev.vars` (alongside the
   `:3001` entries). If missing, add it and the dev server must be restarted to reload.
3. **Test admin** (idempotent): new signups default to role `pending`, which the dashboard rejects.
   Sign up `reviewer@svhc.local` via `POST /api/auth/sign-up/email`, then elevate in local D1:
   `npx wrangler d1 execute DATABASE --local --command "UPDATE users SET role='admin' WHERE email='reviewer@svhc.local';"`
4. **Sign in (browser, MCP)**: navigate to `/sign-in`; the form is in **Portuguese** — fill the
   **Email** + **Senha** textboxes, click **"Entrar"**; expect a redirect to `/dashboard/...`. If
   bounced back to `/sign-in`, check `browser_console_messages`: a **403** on
   `/api/auth/sign-in/email` = origin not trusted (step 2); a **401** = wrong credentials.

Then navigate to the target dashboard path and review. Remove the throwaway account if needed:
`DELETE FROM users WHERE email='reviewer@svhc.local'`.
