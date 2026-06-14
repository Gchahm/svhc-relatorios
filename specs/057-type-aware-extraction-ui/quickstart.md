# Quickstart: Type-aware extraction UI

## What changed

`AttachmentAnalysisDetailDialog` now renders a typed transcription (a stored page `response` carrying
`doc_type`) grouped by the document's structure, with the reconciliation source fields highlighted
and labelled with the role they feed. Legacy flat rows and error rows are unchanged.

## Files

- `src/app/dashboard/entries/typed-transcription.ts` — pure builder (`buildTypedSections`) +
  `RECONCILIATION_PROVENANCE` map + `canonicalDocType`. No React imports beyond types.
- `src/app/dashboard/entries/typed-transcription.test.mjs` — `node:test` unit tests.
- `src/app/dashboard/entries/AttachmentAnalysisDetailDialog.tsx` — consumes the builder in the
  typed branch of `RecordValues`.
- `src/lib/i18n/catalog.ts` — new `analysis.*` section/role label keys (pt-BR + en + type).

## Run the checks

```bash
pnpm test:ts        # node --test "src/**/*.test.mjs" — includes the new builder tests + catalog parity
pnpm lint
pnpm format
```

## Manual verification (browser)

1. Start the app per the project's run convention (`pnpm dev`, or `pnpm preview` for the Workers build).
2. Sign in to the dashboard, open an entry with an analysis, open the analysis detail dialog.
3. Confirm:
   - A typed record renders grouped sections with localized titles; every transcribed value is visible.
   - The reconciliation total and issuer fields carry a provenance badge naming their role.
   - A legacy flat record renders the prior known-field grid (no sections, no badges).
   - No console/runtime error on any record shape.

If the local data has no typed transcription, the unit tests are authoritative for the typed-path
behavior; the browser check confirms the flat path is unregressed and the dialog never crashes.
