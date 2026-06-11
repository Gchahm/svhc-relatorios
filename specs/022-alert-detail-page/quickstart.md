# Quickstart: Dedicated Alert Detail Page

Manual verification (no automated tests — Constitution III). Use the `ui-login` skill to sign in.

## Prerequisites

- Local dev server: `pnpm dev`.
- Local D1 has alerts (the analysis pipeline writes them). The local set includes
  `document_overpayment` (references a document), `attachment_amount_mismatch` /
  `attachment_vendor_mismatch` (ledger vs extracted), `duplicate_entry` / `negative_credit`
  (entry_ids[]), and `vendor_concentration` / `unit_delinquency` / `new_vendor` (no entries) — a good
  spread of metadata shapes.
- Sign in via `ui-login` (admin or member).

## Steps

1. **List unchanged otherwise**: open `/dashboard/alerts`. Confirm filters (severity/period/type/
   status) and the active-count summary still work.
2. **US1 — navigate, don't toggle**: click an active alert row. Confirm the URL becomes
   `/dashboard/alerts/<id>` (a real, shareable path) and the alert's status did **not** change.
3. **US1 — core fields**: confirm the detail page shows title, severity, type, period, created time,
   status, the **full** description (untruncated), resolved timestamp (if resolved), and notes.
4. **US1 — affected entries**: for an alert with entries (e.g. `duplicate_entry`), confirm each entry
   is listed and links to `/dashboard/entries?period=…&entry=…`.
5. **US3 — evidence**: open a `document_overpayment` alert; confirm labeled evidence (total value,
   sum entries, over amount as currency) and a working link to `/dashboard/documents/<id>`. Open an
   `attachment_amount_mismatch`; confirm ledger value vs extracted value shown. Open
   `vendor_concentration`; confirm the percentage renders readably.
6. **US3 — no-evidence**: open an alert with only a description; confirm the page renders cleanly with
   an empty-state (no broken evidence section).
7. **US2 — resolve**: on an active alert, click Resolve, enter a note, confirm it becomes resolved with
   the note and a resolved timestamp.
8. **US2 — reopen**: on that resolved alert, click Reopen; confirm it returns to active and the
   resolved timestamp clears.
9. **US2/FR-009 — list reflects status**: go back to `/dashboard/alerts`; confirm the alert shows its
   new status.
10. **Edge — not found**: visit `/dashboard/alerts/does-not-exist`; confirm a clear "not found" state.
11. **Shareable URL (SC-005)**: copy a detail URL, open in a fresh tab (signed in); confirm it reopens
    the same alert.

## Acceptance

- Row click opens details and never flips status (SC-002).
- Full description + all evidence visible on one page (SC-001).
- Every affected entry and any referenced document reachable in one click (SC-003).
- List reflects status after resolve/reopen (SC-004).

## Gates

- `pnpm lint` and `pnpm format` pass before commit.
