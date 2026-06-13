# Research: Deterministic per-type mappers

## Decision 1 — Mapper output shape: the existing flat reconciliation-field contract

**Decision**: Each per-type mapper returns a dict using the **exact flat field names the analysis
roll-up already reads** off `record.response`: `tipo_documento`, `papel_artefato`, `cnpj_emitente`,
`nome_emitente`, `numero_documento`, `descricao_servico`, `data_emissao`, `valor_total`,
`valor_liquido`, `valor_pago`. The mapper is the function `typed JSON → flat reconciliation fields`.

**Rationale**: `_rollup_attachment_fields`, `_map_artifact_role`, `_pick_payment_amount`,
`_pick_attachment_date`, `_sum_distinct_invoices`, `_attachment_in_period`, and
`nf_total_for_reconciliation` all read these flat keys off each page's `response`. Producing the same
flat shape means the wiring is a single normalization at the boundary — every downstream consumer is
untouched, eliminating regression risk for legacy flat records (which normalize to themselves).

**Alternatives considered**:
- _Rewrite the roll-up to walk typed nested fields directly._ Rejected: touches every consumer,
  high regression surface, and would have to special-case typed vs. flat at each read site.
- _Return a typed dataclass per type._ Rejected: the roll-up consumes loose dicts; a dataclass adds
  ceremony without buying anything the flat dict doesn't, and breaks the legacy pass-through.

## Decision 2 — Dispatch on the `doc_type` discriminator; flat pass-through when absent

**Decision**: A single `to_reconciliation_fields(response)` dispatch reads the `doc_type`
discriminator, resolves it to a canonical type, and calls that type's mapper. When `doc_type` is
**absent**, the record is a legacy flat record and is returned essentially unchanged (only the known
reconciliation keys are projected, so callers see a stable shape). Never raises on any input.

**Rationale**: The typed JSON self-declares its type (`doc_type`, written canonically by the
EXTRACT-001 registry). Coexistence (design §10.4 / T2) is keyed on the discriminator's presence — no
DB `schema_version` column is needed to tell typed from flat. Defensive alias resolution handles a
non-canonical `doc_type` that slipped through; an unknown type falls back to the generic mapper.

**Alternatives considered**:
- _Add a `schema_version` column / sniff on it._ Rejected: no schema change is in scope, and the
  discriminator alone is sufficient and simpler (FR-004, Assumptions).

## Decision 3 — Mappers live app-side, stdlib-only (no `tools/doc_transcribe` import)

**Decision**: New module `scripts/analysis/type_mappers.py`, stdlib-only, importing nothing from
`tools/doc_transcribe`. The small canonical-type alias resolution is **mirrored** locally (a compact
alias map → canonical key), exactly as the scraper mirrors (rather than imports) the analysis
tolerance.

**Rationale**: Design T6 leans app-side ("SVHC reconciliation policy … until a second consumer
appears"). The analysis package is stdlib-only and is run with cwd `scripts/`, so `tools/` is not on
its import path. Mirroring the tiny alias map (≈20 entries) avoids a cross-package dependency for a
trivial lookup; the canonical key set is stable (the six corpus types).

**Alternatives considered**:
- _Import `tools.doc_transcribe.registry.canonical_type`._ Rejected: cross-package import the
  analysis package deliberately avoids; would couple analysis runtime to the tools layout.
- _Ship mappers inside `tools/doc_transcribe`._ Rejected by T6 — "which field SVHC reconciles on" is
  app policy, not portable schema knowledge.

## Decision 4 — Per-type total selection rules

**Decision** (the deterministic mapping, derived from the schemas in `tools/doc_transcribe/schemas`):

| type                    | `valor_total`            | `valor_liquido`          | `valor_pago` | `cnpj_emitente`         | `numero_documento`   | `nome_emitente`     | `data_emissao`              | `descricao_servico`      | `papel_artefato` |
| ----------------------- | ------------------------ | ------------------------ | ------------ | ----------------------- | -------------------- | ------------------- | --------------------------- | ------------------------ | ---------------- |
| `danfe`                 | `totais.valor_total_nota`| —                        | —            | `emitente.cnpj`         | `numero`             | `emitente.nome`     | `data_emissao`              | first `itens[].descricao`| `invoice`        |
| `nfse`                  | `valores.valor_liquido`  | `valores.valor_liquido`  | —            | `prestador.cnpj`        | `numero`             | `prestador.nome`    | `data_emissao`              | `discriminacao_servico`  | `nfse`           |
| `boleto`                | `valor_documento`        | —                        | —            | `beneficiario.cnpj_cpf` | `numero_documento`   | `beneficiario.nome` | `data_documento`            | —                        | `boleto`         |
| `recibo`                | `valor`                  | —                        | —            | `recebedor.cnpj_cpf`    | `numero`             | `recebedor.nome`    | `data`                      | `referente_a`            | `payment_proof`  |
| `comprovante_pagamento` | —                        | —                        | `valor`      | `recebedor.cnpj_cpf`    | `identificador`      | `recebedor.nome`    | `data`                      | —                        | `payment_proof`  |
| `outro`                 | single identified amount | —                        | —            | —                       | —                    | —                   | —                           | `descricao`              | `other`          |

`tipo_documento` is set to the canonical `doc_type` (so the existing `_map_artifact_role` /
`document_type` reads stay meaningful). `papel_artefato` is set per the table so the heterogeneity-aware
roll-up's role buckets (invoice/nfse/boleto/payment_proof) populate correctly.

**Rationale**:
- `nfse → valor_liquido` (not `valor_servico`) is the documented 757dedb0 fix: the page legibly shows
  `valor_liquido = 320`; selecting it deterministically yields 320, never the model's old 800. For
  the corpus where deductions are 0, líquido == serviço, so this is safe; when retentions exist,
  líquido is the amount actually settled, which is the correct reconciliation target.
- `danfe → totais.valor_total_nota` is the universal NF-e total (vNF), per design §10.2.
- `recibo`/`comprovante` are payment proofs → their amount is `valor`; recibo's `valor` is the gross
  it acknowledges (placed in `valor_total`), comprovante's `valor` is the settled amount (`valor_pago`).
- `boleto → valor_documento` is the slip face value.
- `outro` derives `valor_total` from the single `valores_identificados[].valor` when exactly one (or
  the first) is present — best-effort, never raises.

**Issuer (emitente) semantics**: `cnpj_emitente`/`nome_emitente` mean "who issued the fiscal document
/ who is owed". For an invoice that is the emitente/prestador; for a payment proof or boleto it is the
recebedor/beneficiário (the payee) — matching the existing `_pick_issuer_name` payer-exclusion logic.

**Non-positive & string amounts**: every amount is passed through the existing `_parse_brl_value`
(reused), so a `0.0` parses to `0.0` (the roll-up's existing `> 0` guard treats it as missing) and a
currency string parses identically to its numeric form (FR-007).

## Decision 5 — Wiring point: normalize at the record-build boundary, idempotently

**Decision**: Apply `to_reconciliation_fields` at **one boundary** — in `build_attachment_analysis`
(`scripts/analysis/attachments.py`), immediately after the provider returns each page's `parsed`
response: `record.response = to_reconciliation_fields(parsed)`, then
`record.artifact_role = _map_artifact_role(record.response)`. The mapper is **idempotent** on a
legacy flat record (flat-in → same flat-out), so this is a no-op for pre-typed data and a derivation
for typed data. Because the normalized flat dict becomes `record.response`, every downstream
reader — the heterogeneity-aware roll-up and its helpers (`_pick_*`, `_sum_distinct_invoices`,
`_attachment_in_period`), `_map_artifact_role`, the persisted `attachment_analysis_records.response`,
`mismatches.py`, and `documents.py` — consumes flat reconciliation fields unchanged. Additionally,
`nf_total_for_reconciliation` maps each response defensively before reading `valor_total`, so it
also works over **already-persisted** records read back by `documents.build_documents` (which may be
typed if a future EXTRACT-004 stores typed JSON in records).

**Why store flat (not the raw typed JSON) in `attachment_analysis_records.response`**: the typed
transcription is preserved verbatim in the `page_classifications` staging row (the vision step's
output, design §10.5 evidence) — that is untouched here. The rolled-up
`attachment_analysis_records.response` has always held the reconciliation-field contract the roll-up
and UI read; storing the mapped flat dict keeps that contract intact and is the single interpretation
boundary. The rich typed evidence + the type-aware UI renderer are EXTRACT-004 / design §10.4, out of
scope.

**Rationale**: One boundary keeps the change localized and the contract intact (FR-005); idempotence
on flat guarantees the no-regression property (FR-004 / US3) by construction; the defensive map in
`nf_total_for_reconciliation` covers the read-back path.

**Alternatives considered**:
- _Map only inside `_rollup_attachment_fields` (leave `record.response` raw typed)._ Rejected:
  `_map_artifact_role`, `mismatches.py`, `documents.py`, and the persisted records would all still
  see typed JSON and break on flat-key reads — many call sites, high regression risk.

## Decision 6 — Testing

**Decision**: stdlib `unittest` in `scripts/tests/test_type_mappers.py` (pure mapper + dispatch unit
tests, incl. the 757dedb0 case and the `rollup-amount-false-positives.md` Problem A cases) plus
additions to the existing attachment roll-up tests to assert the wired behavior over typed records
and the legacy flat pass-through (no regression). No new dependency; run via `pnpm test:py`.

**Rationale**: Matches the repo's stdlib-`unittest`, pure-seam test convention (CLAUDE.md feature
044). The example transcriptions in `tools/doc_transcribe/examples/*.json` are representative
fixtures the mapper tests can reuse (constructed inline to keep analysis tests independent of the
tools layout).
