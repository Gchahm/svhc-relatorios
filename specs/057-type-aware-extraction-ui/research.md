# Phase 0 Research: Type-aware extraction UI

## Decision 1 — How to make the rendering type-aware without a per-type component zoo

**Decision**: A single pure helper module `typed-transcription.ts` exposes `buildTypedSections(values, t, locale)` returning an ordered list of **sections** (`{ titleKey?, rows }`), where each row is `{ label, value, provenanceRole? }`. The component maps sections → headed grids of `Field`s and adds a provenance badge when `provenanceRole` is set. Section/field labels come from the i18n catalog (the builder receives the `t` translator and resolves label keys itself for known fields, falling back to the verbatim dotted path for unknown keys so nothing is dropped).

**Rationale**: One data-shaped builder + one presentational mapper is simpler (Principle V) than five React components, keeps all rendering logic unit-testable as plain data (the repo's `node:test` + `.test.mjs` pattern), and naturally yields the generic fallback (an unknown type just produces a single section of flattened rows — the feature-055 behavior preserved).

**Alternatives considered**: (a) Five dedicated `<DanfeView/>`/`<NfseView/>` components — rejected: more surface, harder to unit-test, duplicated label logic. (b) Keep the alphabetical flatten and only add highlight badges — rejected: doesn't satisfy FR-001 (organized by structure).

## Decision 2 — Provenance source of truth (UI must not drift from the Python mapper)

**Decision**: Mirror the per-type derivation of `scripts/analysis/type_mappers.py` as a TypeScript constant `RECONCILIATION_PROVENANCE: Record<DocType, Partial<Record<ReconRole, string /*dotted source path*/>>>`. Roles: `total`, `issuer_name`, `issuer_cnpj`, `number`, `date`, `service`. The builder tags a row with the role whose source path equals that row's path. The map is documented in `contracts/provenance.md` and asserted in the unit test against the exact paths the Python mapper reads.

**Rationale**: The repo already mirrors (rather than imports) cross-language invariants — the scraper mirrors the analysis reconciliation tolerance; `type_mappers.py` itself mirrors the registry aliases. TS cannot import Python. The doc-type → source-path map is tiny and stable (six corpus types) and a unit test pins it, so drift is caught. (FR-005)

**Mapped source paths (mirroring `type_mappers.py`):**

| Type   | total ←                       | issuer_name ←        | issuer_cnpj ←            | number ←           | date ←          | service ← |
|--------|-------------------------------|----------------------|--------------------------|--------------------|-----------------|-----------|
| danfe  | `totais.valor_total_nota`     | `emitente.nome`      | `emitente.cnpj`          | `numero`           | `data_emissao`  | `itens[0].descricao` |
| nfse   | `valores.valor_liquido`       | `prestador.nome`     | `prestador.cnpj`         | `numero`           | `data_emissao`  | `discriminacao_servico` |
| boleto | `valor_documento`             | `beneficiario.nome`  | `beneficiario.cnpj_cpf`  | `numero_documento` | `data_documento`| — |
| recibo | `valor`                       | `recebedor.nome`     | `recebedor.cnpj_cpf`     | `numero`           | `data`          | `referente_a` |
| comprovante_pagamento | `valor` (paid) | `recebedor.nome`     | `recebedor.cnpj_cpf`     | `identificador`    | `data`          | — |
| outro  | `valores_identificados[0].valor` | —                | —                        | —                  | —               | `descricao` |

Note: the `itens[0].descricao` and `valores_identificados[0].valor` provenance targets are array-first-element paths; the builder marks them best-effort (only when that index exists) — a missing target simply yields no highlight (FR-006).

## Decision 3 — Section structure per type (from the EXTRACT-001 schemas)

**Decision**: Derive the section grouping from the typed JSON's own top-level nested objects (the schema `$defs`/object properties), with localized section titles for the known groups and verbatim path labels for scalars. Concretely, the builder walks the typed object: a nested object becomes a section (titled by catalog key when known: `emitente/prestador/beneficiario/recebedor/destinatario/tomador/pagador/valores/totais/retencoes/banco`), top-level scalars go in a leading "general" section, and arrays (`itens`, `duplicatas`, `valores_identificados`, `retencoes` numbers) flatten with indexed dotted labels. This keeps the "show ALL the text" guarantee (FR-003) while grouping by structure (FR-001).

**Rationale**: Tying section grouping to the actual object shape (not a hardcoded per-type field list) means a schema field added later still renders (no silent drop), and the generic fallback is the same walk with no known section titles.

**Alternatives considered**: Hardcoding each type's field list — rejected: brittle, drops fields the model emits that aren't in the list, violates FR-003.

## Decision 4 — i18n keys

**Decision**: Add a nested `analysis.typed` block (or flat `analysis.tsection_*` / `analysis.trole_*` keys, whichever matches the catalog's existing flat-key style) for: section titles (issuer/provider/recipient/payer/values/totals/retentions/bank/general/items/duplicates/identified-values) and provenance role labels (reconciliation total, issuer, document number, issue date, service). Both pt-BR and en, kept in parity (enforced by `catalog.test.mjs`). The existing `analysis.full_transcription` heading is reused as the typed-record section wrapper title.

**Rationale**: FR-009 mandates catalog-sourced chrome; the existing `analysis.*` namespace and the parity test already cover this surface.

## Decision 5 — Dual-path + safety

**Decision**: The component's `isTyped(values)` predicate (already present, mirrors Python `is_typed`) gates the new path. Legacy flat → unchanged known-field grid; `{"error"}`/unparseable → unchanged error/no-values branch. The typed builder is wrapped so any thrown error degrades to the generic flatten (defensive — FR-002/SC-004), though the builder is written to never throw on partial shapes.

**Rationale**: Preserves the no-regression guarantee (FR-007/FR-008/SC-003) by leaving the non-typed branches literally untouched.

## Verification approach

Per spec A5 / SC: the seeded e2e synthetic period (`2099-01`) may not contain a typed transcription. The load-bearing behavior (section grouping + provenance per type, dual-path, malformed safety) is verified by **unit tests** of the pure builder (`typed-transcription.test.mjs`) covering all six types + a malformed/partial shape + a legacy flat passthrough check. A manual browser smoke confirms the dialog renders without runtime error against whatever local data exists (typed or flat). If a typed fixture can be cheaply seeded, the ui-reviewer exercises it; otherwise the unit tests are authoritative for SC-001/002/004 and the browser check confirms SC-003 + no-crash.
