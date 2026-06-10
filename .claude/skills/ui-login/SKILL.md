---
model: inherit
description: >-
    Log into the running SVHC dashboard through the Playwright **MCP browser** so you can drive and verify the UI (the dashboard is auth-gated by better-auth). Handles the gotchas: the container port/origin mismatch and ensuring a test admin user exists. Uses only the already-available `mcp__playwright__browser_*` tools plus `wrangler`/`curl` — **no test framework, no new dependency**. Use it for "log into the app", "open /dashboard/documents and check it", or any UI verification via the browser.
argument-hint: "[path to open after login, e.g. /dashboard/documents]"
allowed-tools: Bash, Read, mcp__playwright__browser_navigate, mcp__playwright__browser_snapshot, mcp__playwright__browser_fill_form, mcp__playwright__browser_click, mcp__playwright__browser_take_screenshot, mcp__playwright__browser_console_messages, mcp__playwright__browser_close
context: fork
agent: general-purpose
disable-model-invocation: false
---

# Purpose

Drive the real running app in a browser (via the Playwright **MCP** server) to verify UI changes. The whole `/dashboard/*` area is gated by **better-auth**, so you must log in first. This skill gets you authenticated and lands you on the page you want; from there use `browser_snapshot` / `browser_take_screenshot` / `browser_console_messages` to inspect.

The Playwright MCP browser runs **inside the container**. There is no separate test framework — `mcp__playwright__browser_*` tools are already available.

## Test credentials (local Miniflare only — throwaway admin)

```
email:    reviewer@svhc.local
password: Reviewer-2026!
```

Prefer `TEST_USER_EMAIL` / `TEST_USER_PASSWORD` from the environment if set; otherwise use the above. (These are local-dev-only creds; never used against production.)

## Steps

### 1. Find the dev server (it should already be running)

```bash
for p in 3000 3001; do curl -sS -m5 -o /dev/null -w "$p -> %{http_code}\n" http://localhost:$p/ 2>/dev/null; done
```

A `307`/`200` means it's up (307 = redirect to `/sign-in`). The app runs on **:3000 inside the container** (external `:3001` forwards to it). If nothing responds, ask the user to start it (`pnpm dev`) — don't start a second one (two `next dev` in the same dir corrupt `.next`).

### 2. Make sure the origin is trusted (the #1 cause of a 403 on login)

better-auth checks the request `Origin` against `BETTER_AUTH_TRUSTED_ORIGINS` (in `.dev.vars`). The MCP browser's origin is `http://localhost:3000`, so that must be listed. Check:

```bash
grep BETTER_AUTH_TRUSTED_ORIGINS .dev.vars
```

If `http://localhost:3000` is **not** present, add it (keep the existing `:3001` entries for the user's external access), then ask the user to restart `pnpm dev` so it reloads:

```
BETTER_AUTH_TRUSTED_ORIGINS=http://localhost:3001,http://127.0.0.1:3001,http://localhost:3000,http://127.0.0.1:3000
```

### 3. Ensure the test admin user exists (idempotent)

New better-auth signups default to role `pending`, which the dashboard rejects (allowed roles: `admin`, `member`). Create + elevate only if missing:

```bash
# create (200 = created; 422/"already exists" = fine, skip)
curl -sS -m15 -X POST http://localhost:3000/api/auth/sign-up/email \
  -H 'content-type: application/json' \
  -d '{"email":"reviewer@svhc.local","password":"Reviewer-2026!","name":"Reviewer"}' -w "\nHTTP %{http_code}\n"

# elevate to admin in LOCAL D1 (idempotent)
npx wrangler d1 execute DATABASE --local \
  --command "UPDATE users SET role='admin' WHERE email='reviewer@svhc.local';"
```

### 4. Log in through the browser (MCP)

1. `browser_navigate` → `http://localhost:3000/sign-in`
2. `browser_snapshot` → grab the refs for the **Email** and **Senha** textboxes and the **"Entrar"** button (the form is in Portuguese).
3. `browser_fill_form` the Email + Senha textboxes with the creds.
4. `browser_click` the **"Entrar"** button.
5. Expect a redirect to `/dashboard/...`. If you land back on `/sign-in`, run `browser_console_messages` (level `error`): a **403** on `/api/auth/sign-in/email` means the origin isn't trusted (go back to step 2); a **401** means wrong credentials.

### 5. Open the target and verify

`browser_navigate` to the requested path (default the skill argument, e.g. `/dashboard/documents`). Then inspect with `browser_snapshot` (best for asserting structure/links) and/or `browser_take_screenshot`, and check `browser_console_messages` for errors. When done, `browser_close`.

## Notes

- **Data:** UI pages read from local D1/R2 (Miniflare). To see meaningful data, the period must already be scraped → classified → `apply-extractions` → `analyze`.
- **Deep links:** the alerts page and the documents detail dialog link to `/dashboard/entries?period=<YYYY-MM>&entry=<id>`, which auto-opens the attachment-analysis dialog — handy targets to verify.
- **Creds in `.env`:** the harness may block writing `.env*` files; the creds above are the source of truth. If you want them in `.env`, add `TEST_USER_EMAIL` / `TEST_USER_PASSWORD` yourself and this skill will prefer them.
- The reviewer account is a throwaway local admin; remove with `DELETE FROM users WHERE email='reviewer@svhc.local'` if needed.
