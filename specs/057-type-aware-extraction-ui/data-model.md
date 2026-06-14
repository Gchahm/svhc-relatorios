# Phase 1 Data Model: Type-aware extraction UI

This feature adds no persisted entities. The "model" here is the **view model** the pure builder
produces from a read-only typed transcription, plus the provenance map.

## Input (read-only, existing)

### `AttachmentAnalysisRecord.response` (string | null)

Stored JSON for one page. Two shapes (discriminated by presence of `doc_type`):

- **Typed transcription** — `{ doc_type, schema_version, raw_text, ...per-type nested structure }`.
  Per-type top-level keys (from EXTRACT-001 schemas):
  - `danfe`: `chave_acesso, numero, serie, natureza_operacao, data_emissao, protocolo_autorizacao, emitente{nome,cnpj,...}, destinatario{...}, itens[]{descricao,...}, totais{valor_total_nota,...}, duplicatas[]`
  - `nfse`: `numero, codigo_verificacao, data_emissao, municipio_prestacao, prestador{nome,cnpj,...}, tomador{...}, discriminacao_servico, valores{valor_servico,deducoes,valor_liquido,...}, retencoes{...}`
  - `boleto`: `beneficiario{nome,cnpj_cpf,...}, pagador{...}, banco{...}, valor_documento, data_vencimento, data_documento, nosso_numero, numero_documento, linha_digitavel, codigo_barras`
  - `recibo`: `numero, data, pagador{...}, recebedor{nome,cnpj_cpf,...}, valor, referente_a`
  - `comprovante_pagamento`: `tipo, data, pagador{...}, recebedor{nome,cnpj_cpf,...}, valor, identificador, instituicao`
  - `outro`: `descricao, valores_identificados[]{rotulo,valor}`
- **Legacy flat record** — no `doc_type`; the pre-typed reconciliation keys (`valor_total, valor_liquido, valor_pago, cnpj_emitente, nome_emitente, data_emissao, numero_documento, descricao_servico, tipo_documento, papel_artefato`). Rendered by the existing unchanged flat branch.
- **Error/unparseable** — `{"error": ...}` or invalid JSON. Existing unchanged branch.

## View model (new, produced by `typed-transcription.ts`)

### `ReconRole` (enum-like union)

`"total" | "issuer_name" | "issuer_cnpj" | "number" | "date" | "service"`

### `TypedRow`

| Field | Type | Notes |
|-------|------|-------|
| `path` | `string` | dotted source path (e.g. `valores.valor_liquido`, `itens.0.descricao`) — stable key |
| `label` | `string` | localized label when the leaf key is known; else the verbatim path segment / dotted path |
| `value` | `string` | display string (currency-formatted when the field is a known amount and numeric) |
| `provenanceRole` | `ReconRole \| undefined` | set iff this path is the mapper's source for that role |

### `TypedSection`

| Field | Type | Notes |
|-------|------|-------|
| `key` | `string` | section identity (top-level object key, or `"general"` for top-level scalars) |
| `title` | `string` | localized section title when known; else the verbatim key |
| `rows` | `TypedRow[]` | non-empty rows only (a section with no non-empty rows is omitted) |

### Builder contract

`buildTypedSections(values: Record<string, unknown>, t: Translate, locale: SupportedLocale): TypedSection[]`

- Walks the typed object: top-level scalars → leading `general` section; each top-level nested object → its own section; arrays → flattened indexed rows within a section keyed by the array name.
- Never throws on a partial/odd shape (missing/null sections skipped; non-object where object expected → skipped).
- Tags each row's `provenanceRole` from `RECONCILIATION_PROVENANCE[canonicalType]` by exact path match.
- Drops `doc_type`/`schema_version` from display (they are the discriminator/version chrome, not document content) but keeps `raw_text` as a full-width row.

### `RECONCILIATION_PROVENANCE`

`Record<DocType, Partial<Record<ReconRole, string>>>` — the per-type source-path map mirroring
`scripts/analysis/type_mappers.py` (see `contracts/provenance.md`). The single TS source of truth;
the builder reads it, the unit test pins it.

### `canonicalDocType(value): DocType`

Mirrors `type_mappers._canonical_doc_type` (case/underscore/hyphen-insensitive alias resolution,
unknown → `outro`). Used to pick the provenance row set and to decide known section titles.
