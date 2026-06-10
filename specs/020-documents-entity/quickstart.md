# Quickstart: Real Documents Entity

## Prerequisites

- Local D1/R2 emulated by Miniflare (`pnpm` deps installed; `uv` for the Python CLI).
- At least one period scraped + classified + applied so `attachment_analyses` exist.

## 1. Migrate the schema

```bash
pnpm db:generate          # generates drizzle/0011_*.sql from fiscal.schema.ts
pnpm db:migrate:dev       # applies documents + document_entries locally
```

## 2. Build documents (and links) from analyses

```bash
cd scripts
uv run python -m analysis build-documents          # local; add --remote for prod
```

Verify:
```bash
npx wrangler d1 execute DATABASE --local --command \
  "SELECT count(*) docs FROM documents;"
npx wrangler d1 execute DATABASE --local --command \
  "SELECT count(*) links FROM document_entries;"
```
Expect one document per unique (normalized number, CNPJ) and links to every referencing entry. Re-running `build-documents` must leave both counts unchanged (idempotent).

## 3. Run analysis → overpayment alerts

```bash
cd scripts
uv run python -m analysis analyze                  # builds docs + per-period checks + global overpayment
```

Verify the new alert (and that duplicate_billing is gone):
```bash
npx wrangler d1 execute DATABASE --local --command \
  "SELECT type, count(*) FROM alerts GROUP BY type;"
```
Expect `document_overpayment` rows where linked entries exceed the document total; no `duplicate_billing`.

## 4. Browse the UI

```bash
pnpm dev
```
- Open `/dashboard/documents` (auth-gated). Confirm each row shows number, issuer, type, total, # linked entries, sum, and an over/within/under/unknown status badge.
- Filter by type; search by number/issuer.
- Click a document → dialog lists linked entries; click an entry's deep link → lands on `/dashboard/entries` with that period selected, the row highlighted, and its analysis dialog open.
- Open `/dashboard/alerts`; a `document_overpayment` alert renders per-entry deep links.

## 5. Gates before commit

```bash
pnpm lint && pnpm format
pnpm build                # tsc/Next build must pass
```

## Acceptance mapping

| Check | Where |
|-------|-------|
| One doc per unique (number, CNPJ); no spurious rows | step 2 verify + SC-001 |
| Links accrue across periods | re-run build after another period (SC-002) |
| Overpayment alert + deep links, no duplicate_billing | step 3 + step 4 alerts |
| Idempotent re-run | step 2 re-run counts unchanged (SC-004) |
| Browse/filter/search + drill-in | step 4 (SC-005) |
