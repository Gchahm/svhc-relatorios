# ui-reviewer memory — svhc-relatorios

Repo-specific UI facts I've learned. Read these before a review; update them as I learn more.

## Login (REQUIRED — the dashboard is auth-gated)

The whole `/dashboard/*` area is gated by **better-auth**, so I must authenticate before reviewing
any dashboard page. **Log in by invoking the `ui-login` skill** (Skill tool) with the target path,
e.g. `ui-login /dashboard/documents` — it provisions/elevates a throwaway local admin, fixes the
trusted-origin gotcha, signs in through the **same** MCP browser I review in, and lands me on the
path. Local throwaway creds: `reviewer@svhc.local` / `Reviewer-2026!`. Full steps + gotchas:
[how-to-login](how-to-login.md).

## Running & verifying the app

The app is Next.js 15 on Cloudflare Workers; the dev server runs on **:3000 inside the container**
(external :3001 forwards in). Don't start a second `next dev` in the same dir (it corrupts `.next`).
For the canonical run/verify/lint commands see the constitution's *Running & Verifying the App*
section (`.claude/agent-memory/speckit/constitution.md`). UI strings are **pt-BR / en** (localized).

## Tests / e2e suite — EXTEND this, don't introduce a new one

This repo HAS a browser e2e suite: **`scripts/e2e/`** — **Python Playwright** (`sync_api`), smoke
depth. The browser smoke is `scripts/e2e/smoke.py`; an admin is provisioned by `scripts/e2e/auth.py`;
run via `pnpm test:e2e` (build + serve + smoke) or `pnpm e2e:smoke` against a running app (synthetic
period `2099-01`). **Add UI-review tests to this suite in Python** — do NOT add `@playwright/test` /
a `tests/e2e/*.spec.ts` JS suite or any new dependency. (TS unit tests use `node:test`, Python unit
tests use `unittest`, but the browser/e2e layer is `scripts/e2e/`.)
