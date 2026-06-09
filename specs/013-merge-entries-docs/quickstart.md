# Quickstart: Merge Document Analyses into the Entries page

Manual verification (no automated tests in this repo).

## Run

```bash
pnpm dev   # local dev server
```

Sign in as an `admin` or `member` user and open `/dashboard/entries`.

## Verify

### US1 — match status inline (P1)
1. Select a period that has analysed documents.
2. Entries with an analysed document show amount/vendor/date match badges and a document-type indicator. Entries without one show plain rows (neutral em-dash, **not** "mismatch").
3. An entry whose analysis has a processing error is visibly distinguished from both match and mismatch.

### US2 — detail from an entry (P1)
1. Click an entry that has an analysis → the document-analysis detail dialog opens with extracted fields and page images (same as the old page).
2. Click an entry with no analysis → no dialog opens.
3. Close the dialog → return to the same period view with filters and scroll intact.

### US3 — document filters & summary (P2)
1. Apply "has discrepancy" (match-status) filter → list reduces to entries with ≥1 mismatch or an error.
2. Apply a document-type filter → list reduces to that type.
3. Combine with existing search + category filters → all AND together.
4. Switch period → document filters reset along with entry filters; summary recounts for the new period.
5. The period summary shows mismatch/error counts; cross-check that they equal what the old `/dashboard/document-analyses` page showed for that same period (SC-005).

### US4 — old route & nav (P3)
1. Visit `/dashboard/document-analyses` directly → redirected to `/dashboard/entries`.
2. The top nav no longer has a separate "Docs" item; there is one entry point.

## Pre-commit gates

```bash
pnpm lint
pnpm format
```

Confirm no schema/migration files changed (this feature is read-only).
