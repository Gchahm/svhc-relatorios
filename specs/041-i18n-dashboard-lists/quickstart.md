# Quickstart: verify the dashboard list-page localization

## Prerequisites
- Local D1 has prod-like data (it does in this checkout).
- `pnpm install` already run.

## Run the catalog + lint + format gates
```bash
# catalog completeness (Node test runner)
node --test src/lib/i18n/catalog.test.mjs
# or the project test script
pnpm test

pnpm lint
pnpm exec prettier --check "src/**/*.{ts,tsx,mjs}"
```

## Build (de-risk the client/server import split — R6)
```bash
pnpm build   # must succeed; confirms client bundles don't drag server-only getLocale()
```
If the build complains about `getCloudflareContext`/server-only code in a client bundle, add a
client-safe formatter re-export (see research.md R6) and re-build.

## Manual UI verification (per the PR phase)
Use the `ui-login` skill to log into the running app, then visit each page and confirm pt-BR chrome
with verbatim data:
- `/dashboard/entries` — headers (Data/Descrição/Categoria/Subcategoria/Unidade/Valor), filter
  labels (Período/Pesquisar/Tipo de documento/Status do documento), summary (Receita/Despesa/Saldo),
  count ("N lançamentos", singular at 1), date `DD/MM/AAAA`, currency `R$ 1.234,56`. Sort, filter,
  and an alert→entry deep link still work. Descriptions/vendor names render verbatim.
- `/dashboard/alerts` — severity badges (Crítico/Aviso/Informação), type labels localized (no raw
  snake_case), resolved/active badges (Resolvido/Ativo), filters, count, empty state.
- `/dashboard/documents` — status badge (Acima/Conforme/Abaixo/Desconhecido), filters, count, empty.
- `/dashboard/reports`, `/dashboard/fines`, `/dashboard/comparison`, `/dashboard/summary`,
  `/dashboard/scrape-runs`, `/dashboard/units`, `/dashboard/vendors`, `/dashboard/document-analyses`
  — titles, headers, counts, totals, empty states all pt-BR; money/date/percent in Brazilian format.

## Grep gate (SC-002)
```bash
# No private formatter definitions remain in the listed files:
grep -rnE "function (formatCurrency|formatDate|formatPercent|formatDateTime|formatNumber)" \
  src/app/dashboard/{entries,alerts,documents,reports,fines,comparison,summary,scrape-runs,units,vendors}
# Expect: no matches.

# No raw English chrome literals remain (spot-check a few):
grep -rn "Select period\|Search description\|No alerts found\|No documents found\|Loading\.\.\." \
  src/app/dashboard
# Expect: no matches in the listed clients.
```
