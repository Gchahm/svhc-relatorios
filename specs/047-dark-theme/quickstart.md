# Quickstart: Dark theme

## Prerequisites

- `pnpm install` (adds `next-themes`).
- Local Miniflare D1 with prod-like data (already present in the dev container).

## Try it

1. `pnpm dev` and sign in (see the `ui-login` skill for the test admin).
2. In the dashboard header, find the sun/moon button between the nav and your user menu. Click it.
3. Pick **Escuro** (Dark) — the whole app repaints dark immediately.
4. Reload — it stays dark, no flash of light first.
5. Pick **Sistema** (System) — it matches your OS preference; flip your OS dark mode and watch it follow.
6. Pick **Claro** (Light) — back to light. Close and reopen the tab — your last choice is honored.
7. Walk the surfaces in dark mode: list pages (entries/documents/alerts/vendors/units/fines/reports/summary/comparison/scrape-runs), open a detail page and a dialog, check status/severity badges, and visit the sign-in page — everything legible, nothing white-on-white.

## Verify gates

```bash
pnpm lint
pnpm format        # or: pnpm format:check in CI
node --test src/lib/i18n/catalog.test.mjs   # catalog completeness incl. new theme.* keys
```

## Key files

- `src/components/theme-provider.tsx` — provider (NEW)
- `src/app/layout.tsx` — `suppressHydrationWarning` + provider mount (MODIFY)
- `src/app/dashboard/ThemeToggle.tsx` — header toggle (NEW)
- `src/app/dashboard/layout.tsx` — mounts the toggle; gray→token chrome (MODIFY)
- `src/lib/i18n/catalog.ts` — `theme` namespace (MODIFY)
- Audited dashboard clients — straggler colors → tokens / `dark:` variants
