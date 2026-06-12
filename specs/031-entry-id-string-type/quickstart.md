# Quickstart: Correct `Entry.id` client type to UUID string

## What changed

- `Entry.id` is now `string` (was `number`) — honest against `entries.id` (text UUID).
- The redundant `String(e.id)` / `String(entry.id)` coercions are gone.
- `Entry` and `AttachmentAnalysisRow` now live in `src/app/dashboard/entries/types.ts`;
  `AttachmentAnalysisDetailDialog` and `alerts/[id]/AlertDetailClient` import them from there.

## Verify locally

```bash
pnpm install            # if needed
pnpm lint               # ESLint — must pass clean
node_modules/.bin/next build   # type-check + build (pnpm build equivalent)
pnpm dev                # then open the app
```

Manual checks (via the `verify` skill / browser):

1. Open `/dashboard/entries`, pick a period with rows → rows render, no console error.
2. Apply a document-type filter → only rows whose analysis has that type remain.
3. Follow an alert deep link `/dashboard/entries?period=<YYYY-MM>&entry=<entryId>` → the
   targeted row highlights and its attachment-analysis dialog opens.
4. Click a row that has an analysis (no deep link) → its dialog opens.

## Rollback

Single-commit, type-only change. Revert the commit to restore the prior types and wrappers.
