# Data Model: I18N-004 catalog key inventory

This feature has no D1/runtime data model. The "model" is the set of catalog keys added to
`src/lib/i18n/catalog.ts` (`CatalogShape` + pt-BR canonical + en), plus the keys reused from prior
i18n features. Values below are the intended pt-BR / en strings (final wording may refine during
implement; the test only enforces presence + non-empty).

## New section: `detail` (shared detail-page chrome)

| Key | pt-BR | en |
|-----|-------|-----|
| `detail.loading` | Carregando… | Loading… |
| `detail.back_to_alerts` | Voltar para alertas | Back to alerts |
| `detail.back_to_documents` | Voltar para documentos | Back to documents |
| `detail.alert_not_found` | Alerta não encontrado. | Alert not found. |
| `detail.document_not_found` | Documento não encontrado. | Document not found. |
| `detail.error_prefix` | Erro: | Error: |
| `detail.unknown_error` | Erro desconhecido | Unknown error |
| `detail.field_type` | Tipo | Type |
| `detail.field_period` | Período | Period |
| `detail.field_created` | Criado em | Created |
| `detail.field_resolved_at` | Resolvido em | Resolved at |
| `detail.field_description` | Descrição | Description |
| `detail.field_notes` | Observações | Notes |
| `detail.section_resolution` | Resolução | Resolution |
| `detail.resolved_message` | Este alerta está resolvido | This alert is resolved |
| `detail.reopen_alert` | Reabrir alerta | Reopen alert |
| `detail.reopening` | Reabrindo… | Reopening… |
| `detail.notes_optional_label` | Observações (opcional) | Notes (optional) |
| `detail.notes_placeholder` | Por que isto foi resolvido? (opcional) | Why is this resolved? (optional) |
| `detail.resolve_alert` | Resolver alerta | Resolve alert |
| `detail.resolving` | Resolvendo… | Resolving… |
| `detail.section_evidence` | Evidências | Evidence |
| `detail.view_referenced_document` | Ver documento referenciado | View referenced document |
| `detail.section_affected_entries` | Lançamentos afetados | Affected entries |
| `detail.no_entries_linked` | Nenhum lançamento vinculado a este alerta. | No entries linked to this alert. |
| `detail.field_category` | Categoria | Category |
| `detail.field_subcategory` | Subcategoria | Subcategory |
| `detail.field_vendor` | Fornecedor | Vendor |
| `detail.field_unit` | Unidade | Unit |
| `detail.field_amount` | Valor | Amount |
| `detail.view_attachment` | Ver anexo | View attachment |
| `detail.view_attachment_title` | Ver o anexo e as imagens de suas páginas | View the attachment and its page images |
| `detail.no_attachment_analysis` | Sem análise de anexo | No attachment analysis |
| `detail.documents_button` | Documentos | Documents |
| `detail.attached_documents` | Documentos anexados | Attached documents |
| `detail.no_documents_linked_entry` | Nenhum documento vinculado a este lançamento. | No documents linked to this entry. |
| `detail.field_issuer` | Emitente | Issuer |
| `detail.field_cnpj` | CNPJ | CNPJ |
| `detail.field_total` | Total | Total |
| `detail.field_sum_entries` | Soma dos lançamentos | Sum entries |
| `detail.field_linked_entries` | Lançamentos vinculados | Linked entries |
| `detail.section_document_image` | Imagem do documento | Document image |
| `detail.no_image_available` | Nenhuma imagem disponível | No image available |
| `detail.document_fallback` | Documento | Document |
| `detail.section_source_attachments` | Anexos de origem | Source attachments |
| `detail.from_entry` | Do lançamento | From entry |
| `detail.no_image_for_source` | Sem imagem para esta origem | No image for this source |
| `detail.this_document` | este documento | this document |
| `detail.unlabeled` | Sem rótulo | Unlabeled |
| `detail.section_linked_entries` | Lançamentos vinculados | Linked entries |
| `detail.no_entries_linked_plain` | Nenhum lançamento vinculado. | No entries linked. |
| `detail.col_period` | Período | Period |
| `detail.col_date` | Data | Date |
| `detail.col_description` | Descrição | Description |
| `detail.col_category` | Categoria | Category |
| `detail.col_vendor` | Fornecedor | Vendor |
| `detail.col_unit` | Unidade | Unit |
| `detail.col_amount` | Valor | Amount |
| `detail.col_open` | Abrir | Open |
| `detail.open` | Abrir | Open |
| `detail.section_related_documents` | Documentos relacionados | Related documents |
| `detail.no_related_documents` | Nenhum outro documento está vinculado a estes lançamentos. | No other documents are linked to these entries. |
| `detail.col_number` | Número | Number |
| `detail.col_issuer` | Emitente | Issuer |
| `detail.col_type` | Tipo | Type |
| `detail.col_total` | Total | Total |
| `detail.col_status` | Status | Status |

> Note: several `detail.field_*`/`detail.col_*` overlap conceptually with existing `table.*` keys; per
> A3 the implementation MAY reuse `table.period`/`table.date`/etc. directly instead of adding a
> duplicate. The inventory lists the *needed concepts*; reuse is preferred where an exact existing key
> exists. Implementation will reuse `status.over/within/under/unknown`, `severity.*`, `alert_status.*`,
> `button.close` rather than re-add them.

## New section: `analysis` (attachment-analysis dialog)

| Key | pt-BR | en |
|-----|-------|-----|
| `analysis.dialog_title` | Análise do anexo | Attachment Analysis |
| `analysis.processing_error` | Erro de processamento: | Processing error: |
| `analysis.section_entry_source` | Lançamento (origem) | Entry (source) |
| `analysis.section_rollup` | Consolidado (extraído) | Roll-up (extracted) |
| `analysis.section_pages` | Páginas | Pages |
| `analysis.field_category` | Categoria | Category |
| `analysis.field_subcategory` | Subcategoria | Subcategory |
| `analysis.field_vendor` | Fornecedor | Vendor |
| `analysis.field_date` | Data | Date |
| `analysis.field_description` | Descrição | Description |
| `analysis.field_issuer` | Emitente | Issuer |
| `analysis.field_cnpj` | CNPJ | CNPJ |
| `analysis.field_document_number` | Nº do documento | Document № |
| `analysis.field_service` | Serviço | Service |
| `analysis.field_entry_amount` | Valor do lançamento | Entry amount |
| `analysis.field_document_amount` | Valor do documento | Document amount |
| `analysis.field_gross` | Bruto | Gross |
| `analysis.field_net` | Líquido | Net |
| `analysis.field_paid` | Pago | Paid |
| `analysis.field_issue_date` | Data de emissão | Issue date |
| `analysis.field_doc_type` | Tipo de documento | Doc type |
| `analysis.field_artifact_role` | Papel do artefato | Artifact role |
| `analysis.match_amount` | Valor | Amount |
| `analysis.match_vendor` | Fornecedor | Vendor |
| `analysis.match_date` | Data | Date |
| `analysis.match_ok` | OK | OK |
| `analysis.match_mismatch` | divergência | mismatch |
| `analysis.reconciled_vs_payment` | valor reconciliado com comprovante de pagamento | amount reconciled vs payment artifact |
| `analysis.not_extracted` | não extraído | not extracted |
| `analysis.no_parsed_values` | Sem valores extraídos. | No parsed values. |
| `analysis.parse_error_prefix` | Erro de leitura: | Parse error: |
| `analysis.no_pages_or_records` | Nenhuma página ou registro por página para esta análise. | No pages or per-page records for this analysis. |
| `analysis.page_n` | página {n} | page {n} |

## New section: `viewer` (page-image viewer)

| Key | pt-BR | en |
|-----|-------|-----|
| `viewer.image_unavailable` | Imagem indisponível | Image unavailable |
| `viewer.enlarge` | Ampliar {alt} | Enlarge {alt} |
| `viewer.page_alt` | Página {label} | Page {label} |
| `viewer.page_alt_role` | Página {label} ({role}) | Page {label} ({role}) |
| `viewer.document_image_alt` | Imagem de {type} | {type} image |

> `{alt}`/`{label}`/`{role}`/`{type}` are runtime substitutions done in the component
> (`String.replace`), NOT translated — they carry data/labels passed by the caller.

## Reused existing keys (no addition)

- `status.over` / `status.within` / `status.under` / `status.unknown` — document status badge.
- `severity.*`, `alert_status.*` — already rendered by the shared `SeverityBadge`/`StatusBadge`.
- `button.close` — dialog close (shadcn primitive default).
- `notice.deeplink_invalid` / `notice.deeplink_not_found_prefix` / `_suffix` — entries notice (already
  wired; verify only).

## Catalog test additions (`catalog.test.mjs`)

- Add `"detail"`, `"analysis"`, `"viewer"` to the required-sections list.
- Add an `I18N-004` test asserting the new keys resolve to non-empty strings in **both** locales
  (mirrors the existing I18N-002 / I18N-003 tests).
