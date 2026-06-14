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

To run smoke manually, the server must be on port 3001 (trusted origin). Use `pnpm e2e:smoke` (builds
and starts on :3001). The preview server started by `pnpm preview` defaults to :8787 — NOT trusted.

## Recurring traps / gotchas

- **`pnpm preview` uses port 8787** (not 3000/3001). The e2e smoke suite requires port 3001.
  `pnpm e2e:smoke` handles this; manual `pnpm preview` does not.
- **Locale is hardcoded pt-BR** — `getLocale()` always returns "pt-BR"; there is no locale-switcher
  UI yet. English catalog keys exist and are correct but cannot be tested through the browser.
- **Entry rows are not keyboard-focusable** (tabIndex: -1) — pre-existing a11y gap, not introduced
  by any recent feature. The dialog itself is keyboard-accessible (Close button + image expand button
  are tabbable; Escape closes).
- **All app dialogs lack `DialogDescription`** — Radix fires a console warning on every dialog open.
  The `DialogDescription` component exists in shadcn/ui but is not used anywhere. Pre-existing.
- **Synthetic seed records are legacy flat** — the `analysis_records.response` in `scripts/e2e/synthetic.py`
  uses `tipo_documento`/`numero`/`cnpj`/`valor_total` (no top-level `doc_type`), so `isTyped()` returns
  false for all seeded records. The typed render path (feature 055/057) cannot be exercised with the
  current synthetic seed — add a typed record to `synthetic.py` if you need live typed-path coverage.
- **feature 057 typed-path unit tests are in `src/app/dashboard/entries/typed-transcription.test.mjs`** —
  81 unit tests cover all 6 doc types, provenance map, alias resolution, and robustness. Run with
  `pnpm test:ts`. The browser smoke S3a/S3b covers the flat-path no-regression guard for the same dialog.
- **`extraKeys` in flat records render verbatim** — keys not in `KNOWN_FIELDS` (like `numero`/`cnpj`
  from the seeded synthetic records, vs `numero_documento`/`cnpj_emitente` in KNOWN_FIELDS) appear
  as verbatim label strings in the per-page section. This is intentional behavior, not a bug.
- **`pnpm dev` on :3000 may have stale `.next` cache** — the dev server may show 404 for chunks;
  use the wrangler/Cloudflare Workers build on :8787 (or :3001 via `pnpm e2e:smoke`) for reliable
  auth and correct UI behavior. The :3000 404 errors for static assets appear in the console but
  are caused by the stale Next.js build, not application code.
