# Phase 1 Data Model: Typed document-extraction schema registry

This feature defines a **contract**, not persisted DB entities. The "data model" is the shape of each typed transcription schema, the registry, and the validation result.

## Common envelope (every typed schema)

| Field | JSON type | Required | Notes |
|---|---|---|---|
| `doc_type` | `enum` (single value, e.g. `["danfe"]`) | yes | self-identifies the type; matches the registry key |
| `schema_version` | `enum` (single value, `["1"]`) | yes | == `SCHEMA_VERSION`; coexistence signal |
| `raw_text` | `string` | yes | full transcribed page text — evidence floor + `outro` never-blocks fallback |

All objects declare `additionalProperties: false`. All non-required scalar fields are nullable (`["<type>","null"]`). Amounts are `["number","null"]` (no bounds — R1). No numeric/length/pattern bounds anywhere; no recursive `$ref`.

## danfe (NF-e / DANFE)

- `chave_acesso` (string|null), `numero` (string|null), `serie` (string|null), `natureza_operacao` (string|null), `data_emissao` (string|null)
- `emitente` (object|null): `nome`, `cnpj`, `ie`, `endereco` (all string|null)
- `destinatario` (object|null): `nome`, `cnpj_cpf`, `endereco` (all string|null)
- `itens` (array of `item`): `descricao` (string|null), `ncm` (string|null), `cfop` (string|null), `quantidade` (number|null), `valor_unitario` (number|null), `valor_total` (number|null)
- `totais` (object|null): `valor_produtos`, `base_calculo_icms`, `valor_icms`, `valor_frete`, `valor_total_nota` (all number|null) — `valor_total_nota` is the vNF the mapper will later read
- `duplicatas` (array of `duplicata`): `numero` (string|null), `vencimento` (string|null), `valor` (number|null)

## nfse (DANFSe)

- `numero` (string|null), `codigo_verificacao` (string|null), `data_emissao` (string|null)
- `prestador` (object|null): `nome`, `cnpj`, `im` (all string|null)
- `tomador` (object|null): `nome`, `cnpj_cpf` (string|null)
- `discriminacao_servico` (string|null)
- `valores` (object|null): `valor_servico`, `deducoes`, `base_calculo`, `aliquota_iss`, `valor_iss`, `valor_liquido` (all number|null) — `valor_liquido` is what the nfse mapper later reads
- `retencoes` (object|null): `irrf`, `inss`, `csll`, `pis`, `cofins`, `iss` (all number|null)

## boleto

- `beneficiario` (object|null): `nome`, `cnpj_cpf` (string|null)
- `pagador` (object|null): `nome`, `cnpj_cpf` (string|null)
- `valor_documento` (number|null), `data_vencimento` (string|null), `data_documento` (string|null)
- `nosso_numero` (string|null), `numero_documento` (string|null), `linha_digitavel` (string|null), `codigo_barras` (string|null)

## recibo

- `numero` (string|null), `data` (string|null)
- `pagador` (object|null): `nome`, `cnpj_cpf` (string|null)
- `recebedor` (object|null): `nome`, `cnpj_cpf` (string|null)
- `valor` (number|null), `referente_a` (string|null)

## comprovante_pagamento (PIX / TED / DOC / boleto pago)

- `tipo` (enum: `pix|ted|doc|boleto|outro` plus `null`)
- `data` (string|null)
- `pagador` (object|null): `nome`, `cnpj_cpf` (string|null)
- `recebedor` (object|null): `nome`, `cnpj_cpf` (string|null) — the beneficiário/favorecido (the issuer for reconciliation)
- `valor` (number|null), `identificador` (string|null — end-to-end / autenticação), `instituicao` (string|null)

## outro (generic fallback — never blocks)

- `descricao` (string|null)
- `valores_identificados` (array of `valor_rotulado`): `rotulo` (string|null), `valor` (number|null)
- (`raw_text` from the common envelope is the required content; everything else is best-effort)

## Registry (entity)

- `SCHEMA_VERSION: str` = `"1"`.
- `DOC_TYPES: tuple[str, ...]` = the six canonical keys.
- `ALIASES: dict[str, str]` — flat-taxonomy + spelling variants → canonical key (R4).
- `schema_for(doc_type: str | None) -> dict` — resolves alias/unknown → `outro`; never raises.
- `load_schema(doc_type) -> dict` / `supported_types() -> tuple[str,...]` — accessors. Schemas loaded from the `schemas/*.json` files (cached).

## Validation result (entity)

- `validate(payload, schema) -> list[str]` — located error strings; empty == valid.
- `validate_transcription(payload, doc_type) -> list[str]` — resolve schema via registry, then `validate`.
- Error string format: `"<json-path>: <reason>"`, e.g. `"$.totais.valor_total_nota: expected number or null, got str"`, `"$: missing required field 'doc_type'"`, `"$.itens[0]: unexpected key 'foo'"`, `"$.doc_type: 'xx' not in enum ['danfe']"`.
