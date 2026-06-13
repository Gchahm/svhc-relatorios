# Quickstart: Verify Vision Extraction Provenance

Presentation-layer feature; no migration, no data backfill.

## Unit (fast, no app)

```bash
node --test src/lib/documents.test.mjs
node --test src/lib/i18n/catalog.test.mjs   # catalog completeness incl. new keys
```

Expect the new selection-rule cases to pass: gross-wins, first-confident-gross, roll-up fallback, none, BRL-string parsing, and max-across-analyses attribution.

## Local app (the real surfaces)

1. Seed the synthetic period and serve the Workers build:
   ```bash
   pnpm e2e:seed        # local Miniflare D1/R2, synthetic period 2099-01
   pnpm preview         # or the e2e server
   ```
   Sign in (see the `ui-login` skill) — the dashboard is auth-gated.

2. **Story 1 + 2 (document)** — open a document whose total disagrees with its page image (the issue's example: `/dashboard/documents/<id>` showing total R$800 while the NF page shows R$320, or any seeded over/under document):
   - The header shows the total **and** a provenance line, e.g. "from page p3 · invoice gross" (or "roll-up estimate" / "no AI total derived").
   - A "view AI extraction" control opens the existing dialog showing each page's extracted `valor_total`/`valor_liquido`/`valor_pago` next to the page image — so it's clear the R$800 was read by the AI from a specific page/field.
   - Confirm the attributed value equals `totalValue` (compare against the pipeline): the provenance is consistent with `nf_total_for_reconciliation`.

3. **Edge cases**:
   - A document with no analyzed attachment → no extraction control (or disabled with a reason), no error.
   - A document whose pages have parse errors → the dialog opens and shows the errors, not an empty view.

4. **Story 3 (alert)** — open a total-driven alert (e.g. `document_overpayment`):
   - The disputed total figure is labelled AI-extracted.
   - The per-entry "View Attachment" button still opens the same extraction dialog.

5. All labels render in pt-BR.

## Gates before PR

```bash
pnpm lint
pnpm format
```
Confirm no new English literals on the affected surfaces and no schema/migration files were generated.
