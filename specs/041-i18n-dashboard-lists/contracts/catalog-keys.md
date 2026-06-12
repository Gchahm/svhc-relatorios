# Contract: Catalog keys consumed by the dashboard list pages

This is the contract the catalog-completeness test (`src/lib/i18n/catalog.test.mjs`) enforces:
every key below MUST exist as a non-empty string in BOTH `pt-BR` and `en`. The exact key set
is finalized during implementation against each file; new keys discovered while editing are
added here and to the test's required-key list. pt-BR values shown; en in parentheses where
useful.

## Page titles/descriptions (`page.*`) — server `t()` in each `page.tsx`
- `page.reports_title` "Prestações de Contas"; `page.reports_description`
- `page.fines_title` "Multas"; `page.fines_description`
- `page.comparison_title` "Comparação"; `page.comparison_description`
- `page.summary_title` "Resumo"; `page.summary_description`
- `page.runs_title` "Execuções"; `page.runs_description`
- `page.units_title` "Unidades"; `page.units_description`
- `page.vendors_title` "Fornecedores"; `page.vendors_description`
- `page.document_analyses_title` "Análises de Documentos"; `page.document_analyses_description`
- (entries/documents/alerts titles already exist.)

## Common chrome
- `form.loading` already exists ("Carregando...") — use for every "Loading..." literal.
- `form.no_results` "Nenhum resultado encontrado" — base for empty states; per-noun variants:
  `form.no_alerts` "Nenhum alerta encontrado", `form.no_documents` "Nenhum documento encontrado",
  `form.no_entries`, `form.no_fines`, `form.no_vendors`, `form.no_units`, `form.no_runs`.
- `form.all` "Todos" — MultiSelect/Select `placeholder="All"`.
- `form.all_types` "Todos os tipos" — documents Type select.
- `error.generic_prefix` "Erro" — the `Error: {error}` blocks → `${t("error.generic_prefix")}: ${error}`.

## Table column headers (`table.*`)
- entries: `table.date`, `table.description`, `table.category`, `table.subcategory`, `table.unit`,
  `table.doc`, `table.amt`, `table.vnd`, `table.dt`, `table.amount`, `table.total`.
- alerts: `table.period`, `table.severity`, `table.title`, `table.description`, `table.entries`,
  `table.status`.
- documents: `table.number`, `table.issuer`, `table.type`, `table.total`, `table.sum_entries`,
  `table.links`, `table.status`.
- reports: `table.period`, `table.revenue`, `table.expenses`, `table.month_balance`,
  `table.accumulated_balance`.
- fines: `table.period`, `table.date`, `table.unit`, `table.reason`, `table.amount`.
- comparison/summary/units/vendors/scrape-runs/document-analyses: headers as found in each file
  (e.g. `table.run`, `table.executed_at`, `table.periods_scraped`, `table.attachments`,
  `table.errors`, `table.name`, `table.share`) — finalized during implementation.

## Filter group labels (`filter.*`)
- `filter.period` "Período", `filter.search` "Pesquisar", `filter.document_type` "Tipo de documento",
  `filter.attachment_status` "Status do documento", `filter.severity` "Severidade",
  `filter.type` "Tipo", `filter.status` "Status", `filter.block` "Bloco", `filter.reason` "Motivo".

## Document reconciliation status (`status.*`) — `StatusBadge.tsx`, DocumentsClient
- `status.over` "Acima", `status.within` "Conforme", `status.under` "Abaixo", `status.unknown` "Desconhecido".

## Alert severity (`severity.*`) — `alerts.tsx` SeverityBadge, AlertsClient filters + counts
- `severity.critical` "Crítico", `severity.warning` "Aviso", `severity.info` "Informação".

## Alert resolved state (`alert_status.*`) — `alerts.tsx` StatusBadge, AlertsClient filter
- `alert_status.active` "Ativo", `alert_status.resolved` "Resolvido".

## Attachment match status (`match.*`) — EntriesClient
- `match.all_match` "Todos conferem", `match.has_mismatch` "Com divergência",
  `match.has_error` "Com erro", `match.amount` "valor", `match.vendor` "fornecedor",
  `match.date` "data", `match.errors` "erros", `match.docs` "docs".

## Pluralized counts (`count.*_one` / `count.*_other`)
- `count.entries_one` "lançamento" / `count.entries_other` "lançamentos"
- `count.alerts_one` "alerta" / `count.alerts_other` "alertas"
- `count.documents_one` "documento" / `count.documents_other` "documentos"
- `count.fines_one` "multa" / `count.fines_other` "multas"
- `count.periods_one` "período" / `count.periods_other` "períodos"
- `count.units_one` "unidade" / `count.units_other` "unidades"
- `count.vendors_one` "fornecedor" / `count.vendors_other` "fornecedores"
- `count.runs_one` "execução" / `count.runs_other` "execuções"

## Entries summary prefixes (`summary.*` or reuse) — EntriesClient header badges
- `summary.revenue` "Receita", `summary.expenses` "Despesa", `summary.net` "Saldo",
  `summary.total` "Total".

## Alert evidence/metadata labels (`meta.*`) — `alerts.tsx` KEY_LABELS
- `meta.total_value` "Total do documento", `meta.sum_entries` "Soma dos lançamentos",
  `meta.over_amount` "Valor excedente", `meta.total` "Total", `meta.vendor_total` "Total do fornecedor",
  `meta.total_expenses` "Total de despesas", `meta.ledger_value` "Valor no livro",
  `meta.extracted_value` "Valor extraído", `meta.pct` "Participação", `meta.rate_pct` "Taxa",
  `meta.count` "Contagem", `meta.paying` "Pagantes", `meta.delinquent` "Inadimplentes",
  `meta.kind` "Tipo", `meta.vendor_name` "Fornecedor", `meta.vendor_id` "ID do fornecedor",
  `meta.document_number` "Nº do documento", `meta.issuer_cnpj` "CNPJ do emitente",
  `meta.date` "Data", `meta.description` "Descrição", `meta.movement_type` "Movimento".
- (These live in `alerts.tsx`, a listed file. `alerts.tsx` is server-importable; the metadata
  evidence grid is consumed by the alert detail page — localizing it here is in-scope because the
  literals are in a listed file, and keeps the glossary centralized. The detail-page *layout* stays
  I18N-004.)

## Misc literals in listed files
- EntriesClient deep-link notice text (in-file): `notice.deeplink_invalid`,
  `notice.deeplink_not_found_prefix`/`_suffix`, `notice.dismiss` (aria-label).
- EntriesClient row titles: `entries.click_attachment_detail` "Clique para ver o documento".
- AlertsClient row title "Click to open the alert detail page" → `alerts.open_detail`.
- AlertsClient `EntryLinks`: "Open" → `action.open`; "N entries ▾" uses `count.entries`;
  "Entry {i+1}" → `entries.entry_n` (with the index appended).
- DocumentsClient title suffix "(Notas Fiscais)" — keep as a localized `documents.subtitle` or
  fold into `page.documents_title`; decided during implementation (data term "Notas Fiscais" is a
  domain label, kept verbatim in pt-BR).

## Notes
- `getAlertTypeLabel` / `alert.types.*` already localized (I18N-001). Replace `alertTypeLabel()`
  from `@/lib/alerts` in AlertsClient with the catalog path; add a non-snake_case fallback.
- Every key added here is mirrored into `en` and added to the completeness test's required list.
