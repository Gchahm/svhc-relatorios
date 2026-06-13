# Data Model: Deterministic per-type mappers

No persisted data model change — **no DB schema change, no migration**. This feature operates on
in-memory dicts at the analysis interpretation seam.

## Typed transcription JSON (input)

A per-page record's `response` dict, self-declaring its type via a `doc_type` discriminator. Shapes
mirror `tools/doc_transcribe/schemas/<type>.json` (EXTRACT-001). Relevant fields per type:

- **danfe**: `numero`, `data_emissao`, `emitente.{nome,cnpj}`, `itens[].descricao`,
  `totais.valor_total_nota`.
- **nfse**: `numero`, `data_emissao`, `prestador.{nome,cnpj}`, `discriminacao_servico`,
  `valores.{valor_servico,valor_liquido}`, `retencoes.*`.
- **boleto**: `numero_documento`, `data_documento`, `beneficiario.{nome,cnpj_cpf}`, `valor_documento`.
- **recibo**: `numero`, `data`, `recebedor.{nome,cnpj_cpf}`, `valor`, `referente_a`.
- **comprovante_pagamento**: `identificador`, `data`, `recebedor.{nome,cnpj_cpf}`, `valor`.
- **outro**: `descricao`, `valores_identificados[].{rotulo,valor}`.

## Legacy flat record (input, coexisting)

A per-page record's `response` dict with **no `doc_type`** key — the pre-typed contract:
`papel_artefato`, `tipo_documento`, `valor_total`, `valor_liquido`, `valor_pago`, `cnpj_emitente`,
`nome_emitente`, `data_emissao`, `numero_documento`, `descricao_servico` (see
`page_classifications.REQUIRED_KEYS`).

## Reconciliation fields (output of the mapper)

A flat dict the analysis roll-up consumes, with these keys (any may be `None`):

| field               | type            | meaning                                                   |
| ------------------- | --------------- | --------------------------------------------------------- |
| `tipo_documento`    | str \| None     | canonical document type                                   |
| `papel_artefato`    | str \| None     | artifact role (invoice/nfse/boleto/payment_proof/other)   |
| `cnpj_emitente`     | str \| None     | issuer/payee CNPJ                                          |
| `nome_emitente`     | str \| None     | issuer/payee name                                         |
| `numero_documento`  | str \| None     | document number / payment identifier                      |
| `descricao_servico` | str \| None     | service / reference description                           |
| `data_emissao`      | str \| None     | document/settlement date (dd/mm/yyyy as transcribed)      |
| `valor_total`       | num/str \| None | gross/face total (the reconciliation total)               |
| `valor_liquido`     | num/str \| None | net total when distinct (nfse)                            |
| `valor_pago`        | num/str \| None | settled amount (payment proofs)                           |

Amounts are emitted as-is (numeric or currency string) and parsed downstream by the existing
`_parse_brl_value`, so the mapper introduces no parsing divergence.

## Mapper / dispatch (behavior, not persisted)

- `to_reconciliation_fields(response: dict) -> dict` — dispatch: canonicalizes `response["doc_type"]`,
  calls the per-type mapper; flat pass-through when `doc_type` is absent; never raises.
- One pure function per type (`_map_danfe`, `_map_nfse`, `_map_boleto`, `_map_recibo`,
  `_map_comprovante`, `_map_outro`).
- `_canonical_doc_type(value) -> str` — local alias→canonical resolution mirroring the registry's
  six-type taxonomy (no `tools` import).
