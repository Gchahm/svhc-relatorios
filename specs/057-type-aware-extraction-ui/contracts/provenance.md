# Contract: Reconciliation provenance map

This is the authoritative UI-side mirror of `scripts/analysis/type_mappers.py`. The TypeScript
constant `RECONCILIATION_PROVENANCE` in `src/app/dashboard/entries/typed-transcription.ts` MUST
match this table exactly, and `typed-transcription.test.mjs` MUST assert it field-by-field. If the
Python mapper changes a derivation, this table, the TS constant, and the test update together.

Roles: `total` (the reconciliation total the alert math uses), `issuer_name`, `issuer_cnpj`
(who issued / who is owed), `number`, `date`, `service`.

| DocType                 | total                              | issuer_name        | issuer_cnpj             | number             | date            | service                 |
|-------------------------|------------------------------------|--------------------|-------------------------|--------------------|-----------------|-------------------------|
| `danfe`                 | `totais.valor_total_nota`          | `emitente.nome`    | `emitente.cnpj`         | `numero`           | `data_emissao`  | `itens.0.descricao`     |
| `nfse`                  | `valores.valor_liquido`            | `prestador.nome`   | `prestador.cnpj`        | `numero`           | `data_emissao`  | `discriminacao_servico` |
| `boleto`                | `valor_documento`                  | `beneficiario.nome`| `beneficiario.cnpj_cpf` | `numero_documento` | `data_documento`| —                       |
| `recibo`                | `valor`                            | `recebedor.nome`   | `recebedor.cnpj_cpf`    | `numero`           | `data`          | `referente_a`           |
| `comprovante_pagamento` | `valor`                            | `recebedor.nome`   | `recebedor.cnpj_cpf`    | `identificador`    | `data`          | —                       |
| `outro`                 | `valores_identificados.0.valor`    | —                  | —                       | —                  | —               | `descricao`             |

Notes:

- Paths use the builder's dotted convention; array indices are numeric segments (`itens.0.descricao`).
- For `comprovante_pagamento` the mapper writes `valor` to `valor_pago` (paid) rather than `valor_total`; the UI role is still "reconciliation total" semantically (the amount the document settles), labelled accordingly. The highlight target path is `valor`.
- A `—` means the mapper derives no value for that role for that type → the UI shows no highlight for it.
- A provenance target that is absent/null in a given record yields no highlight (FR-006); an array-first-element target (`itens.0.descricao`, `valores_identificados.0.valor`) highlights only when that index exists.
- `canonicalDocType` resolves aliases (e.g. `nf-e`/`nfe` → `danfe`, `nfs-e`/`danfse` → `nfse`, `pix`/`ted`/`comprovante` → `comprovante_pagamento`) and unknown → `outro`, mirroring `type_mappers._canonical_doc_type`.
