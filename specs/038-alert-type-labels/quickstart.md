# Quickstart: Shared alert type → label map

## What changed

- New `src/lib/alerts.ts` — `alertTypeLabel(type)` + `ALERT_TYPE_LABELS`.
- `AlertsClient.tsx` Type filter options now show friendly labels.
- `AlertDetailClient.tsx` Type field now shows the friendly label.

## Verify in the running app

1. Log in: use the `ui-login` skill (handles the container port/origin + test admin).
2. Open `/dashboard/alerts`, open the **Type** filter — every option reads as a human-readable label
   (no underscores). Select one — the list still filters correctly.
3. Click any alert row → detail page → the **Type** field shows the same friendly label.

## Run the unit test

```bash
node --test "src/**/*.test.mjs"     # or: pnpm test
```

Expect the `alerts.test.mjs` cases (curated lookup, fallback transform, empty string, non-snake
word, no-throw) to pass.

## Lint / format before commit

```bash
pnpm lint
pnpm format
```
