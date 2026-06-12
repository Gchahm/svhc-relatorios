# Quickstart: Entries deep-link not-found notice

## What changed

The entries page now gives explicit feedback when an alert deep-link
(`/dashboard/entries?period=<YYYY-MM>&entry=<id>`) cannot land on its target entry, instead of
failing silently.

## Try it locally

Prereq: local D1 has prod-like data; log in via the `ui-login` skill (or `pnpm dev` + sign in).

1. **Success (unchanged)** — open a real alert's "view affected entry" link, OR
   `/dashboard/entries?period=<P>&entry=<real-id-in-P>`. The row scrolls into view, highlights
   amber, and (if it has an attachment analysis) the detail dialog opens. No notice.
2. **Not found** — `/dashboard/entries?period=<P>&entry=<valid-uuid-not-in-P>`. An amber
   dismissible banner appears above the list: "Entry <id…8> not found in <P> — it may have been
   removed or re-scraped." The list stays fully usable. The `entry`/`period` params disappear from
   the address bar; a refresh does not re-show the banner.
3. **Filtered out** — open a real entry deep-link, then (before it resolves is hard, so instead)
   apply a search/subcategory filter that hides a known entry and open that entry's deep-link:
   the page clears the filters so the row reappears and highlights — no "not found".
4. **Invalid param** — `/dashboard/entries?period=<P>&entry=not-a-uuid`. A banner reports the link
   was invalid; no row lookup runs. Params are stripped from the URL.

## Run the unit test

```bash
node --test "src/**/*.test.mjs"     # or: pnpm test
```

`src/app/dashboard/entries/deepLink.test.mjs` pins `isValidEntryId`, `shortenEntryId`, and the
`resolveDeepLink` decision table.

## Quality gates

```bash
pnpm lint
pnpm format
```

## Files

- `src/app/dashboard/entries/deepLink.ts` — pure helpers (new)
- `src/app/dashboard/entries/deepLink.test.mjs` — unit tests (new)
- `src/app/dashboard/entries/EntriesClient.tsx` — deep-link effect + notice UI (modified)
