# Contract: Page-extraction field set (frozen)

The agent MUST emit exactly these fields per page. This is the same contract the VLM produced; it is
consumed by `_map_artifact_role` and `_rollup_document_fields` and persisted under
`document_analysis_records.response`. Changing it would break the roll-up, the import, and the
checks — it is frozen for this feature.

| Field               | Type                 | Meaning                                                               | Absent value |
| ------------------- | -------------------- | --------------------------------------------------------------------- | ------------ |
| `papel_artefato`    | enum string          | `invoice` \| `nfse` \| `boleto` \| `payment_proof` \| `other`         | `"other"`    |
| `tipo_documento`    | string               | `NF-e` \| `DANFE` \| `boleto` \| `recibo` \| `comprovante` \| `outro` | `null`       |
| `valor_total`       | number \| BRL string | gross/total value                                                     | `null`       |
| `valor_liquido`     | number \| BRL string | net value after retentions (ISS/INSS/IR)                              | `null`       |
| `valor_pago`        | number \| BRL string | amount actually paid (payment proofs only)                            | `null`       |
| `cnpj_emitente`     | string               | issuer CNPJ, `XX.XXX.XXX/XXXX-XX`                                     | `null`       |
| `nome_emitente`     | string               | issuer company name                                                   | `null`       |
| `data_emissao`      | string               | emission date, `DD/MM/YYYY`                                           | `null`       |
| `numero_documento`  | string               | document number                                                       | `null`       |
| `descricao_servico` | string               | brief description of service/product                                  | `null`       |

## Rules

1. **One page at a time.** Each object describes a single page image; classify what _that_ page is.
2. **No fabrication (FR-011).** If a field is not visible/legible, return `null` — never guess.
3. **Amounts.** Prefer numeric, but BRL strings (`"R$ 1.234,56"`) are accepted; downstream
   `_parse_brl_value` normalizes both. A spurious `0` is treated as missing downstream, so emit
   `null` rather than `0` for an absent amount.
4. **Role reconciliation downstream.** `papel_artefato` may be refined by `_map_artifact_role`
   (e.g. a populated `valor_pago` or a `comprovante`/`recibo` `tipo_documento` forces
   `payment_proof`). The agent should still classify as best it can; it need not replicate that
   reconciliation.
5. **Whole-page failure** is expressed at the file level as `{ "error": "<reason>" }` for that
   page's `path` (see `extractions.schema.md`), not as an all-null fields object.
