# Quickstart: Dedicated Document Detail Page

Manual verification (no automated tests in this repo — Constitution III). Use the `ui-login` skill to
sign in to the running dashboard.

## Prerequisites

- Local dev server: `pnpm dev` (or `pnpm preview` for the Cloudflare runtime).
- At least one built document with linked entries in local D1. If absent, run the scrape + analysis
  pipeline (`python -m scraper scrape --download-docs`, then the `analyze-docs` flow, which runs
  `build-documents`). Pick the best case: a document whose entries are *also* linked to another
  document (so the related-documents section is non-empty).
- Sign in via the `ui-login` skill (admin or member role).

## Steps

1. **Navigate to the list**: open `/dashboard/documents`. Confirm the list still filters by type and
   searches by number/issuer.
2. **US1 — open the detail page**: click a document row. Confirm the URL becomes
   `/dashboard/documents/<id>` (a real, shareable path) and a detail page renders — **not** a dialog.
3. **US1 — header**: confirm the header shows number, issuer name + CNPJ, type, total, sum of linked
   entries, and the over/within/under/unknown status badge.
4. **US1 — entries**: confirm every linked entry is listed with period, date, description, live
   amount, category, subcategory, vendor, and unit. Count matches the list's "Links" column.
5. **US1 — image**: confirm the document's page image(s) render. For a document backed by more than
   one source attachment, confirm each distinct source's image is reachable/shown.
6. **US2 — related documents**: confirm the related-documents section lists other documents linked to
   the same entries — and does **not** include the current document or any raw attachment. Click one
   and confirm it navigates to that document's detail page.
7. **US3 — entry deep link**: from a linked entry, activate its "open in entries" affordance; confirm
   it lands on `/dashboard/entries?period=…&entry=…` focused on that entry.
8. **Edge — not found**: visit `/dashboard/documents/does-not-exist`; confirm a clear "not found"
   state (no crash, no infinite spinner).
9. **Edge — no image**: open a document whose source attachment has no images; confirm the header,
   entries, and related documents still render with a graceful "no image" state.
10. **Edge — zero links**: open a document with no linked entries (if any); confirm the header renders
    and both lists show empty states.
11. **Shareable URL (SC-005)**: copy the detail URL, open it in a fresh tab (still signed in); confirm
    it reopens the same document directly.

## Acceptance

- One navigation reveals all linked entries (SC-001/SC-002): a 10-entry document needs no per-entry
  hopping.
- Related documents reachable in one click (SC-003).
- Image + identity + entries visible together (SC-004).

## Gates

- `pnpm lint` and `pnpm format` pass before commit.
