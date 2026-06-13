# Phase 0 Research: Typed document-extraction schema registry

## R1 — Structured-output subset (the keyword whitelist/blacklist)

**Decision.** Schemas use only: `type` (incl. `["<type>","null"]` unions), `properties`, `required`, `items`, `enum`, `const`-via-single-value-`enum`, `anyOf`, `$ref` (into `$defs`), `additionalProperties: false` on every object, `title`/`description` (annotations, ignored by validation), `$defs`, `$schema`. **Disallowed** (must not appear anywhere): `minimum`, `maximum`, `exclusiveMinimum`, `exclusiveMaximum`, `multipleOf`, `minLength`, `maxLength`, `pattern`, `minItems`, `maxItems`, `uniqueItems`, `minProperties`, `maxProperties`, `format` (as a constraint), `if`/`then`/`else`, `not`, `allOf`, `oneOf`, recursive `$ref`.

**Rationale.** Design §11.3 + the `claude-api` skill: the Anthropic structured-output feature supports objects/arrays/enums/`anyOf`/`$ref` and requires `additionalProperties:false`, but strips/rejects numeric/length bounds and recursion. Keeping the schema within this subset means the *same* schema file is the prompt spec, the wire `output_config` schema, and the local validation target — no divergence.

**Alternatives considered.** Use full JSON Schema and let the SDK strip — rejected: silent stripping changes meaning and the `cli` backend has no wire enforcement at all, so an unsupported keyword would just be ignored locally too. Better to forbid it and assert the subset in a test (FR-007).

## R2 — Validator implementation (stdlib only)

**Decision.** A small recursive validator in `validator.py` implementing exactly the R1 keyword subset: `type` (mapping JSON types to Python types, treating `int`/`float` as `number`, and `bool` as NOT a number — JSON `true`/`false` are only `boolean`), nullable unions, `enum`, `required`, `properties` + `additionalProperties:false`, `items`, `anyOf` (passes if any branch passes), and `$ref` resolution against the schema's `$defs`. Returns `list[str]` of located error messages (path like `$.totais.valor_total_nota`); empty == valid. A separate `validate_transcription(payload, doc_type)` resolves the schema via the registry first.

**Rationale.** FR-005 forbids a new pip dependency and the `analysis` package is stdlib-only; the design (T1/T5) explicitly leans "JSON Schema as spec + lightweight stdlib validation." Because the schemas are confined to R1, a full engine is unnecessary — implementing only the used subset keeps it ~120 lines and fully unit-testable. `$ref` is non-recursive (R1), so resolution terminates without cycle tracking, but we still guard depth defensively.

**Alternatives considered.** `jsonschema` PyPI package — rejected (new dependency, violates FR-005/SC-005). `referencing`/draft-2020 full validation — overkill for the subset.

## R3 — Canonical field layouts per document type

**Decision.** Mirror the real Brazilian national-standard layouts (NF-e/DANFSe are SEFAZ standards). Each schema has a required `doc_type` (single-value enum) + `schema_version` (single-value enum) + a `raw_text` string (full transcribed page text, always present as the evidence/fallback floor), then type-specific blocks:

- **danfe**: `chave_acesso` (string|null, 44 digits transcribed as text — NOT length-bounded per R1), `numero`, `serie`, `natureza_operacao`, `data_emissao`, `emitente`{nome, cnpj, ie, endereco}, `destinatario`{nome, cnpj_cpf, endereco}, `itens`[]{descricao, ncm, cfop, quantidade, valor_unitario, valor_total}, `totais`{valor_produtos, base_calculo_icms, valor_icms, valor_frete, valor_total_nota}, `duplicatas`[]{numero, vencimento, valor}.
- **nfse**: `numero`, `codigo_verificacao`, `data_emissao`, `prestador`{nome, cnpj, im}, `tomador`{nome, cnpj_cpf}, `discriminacao_servico`, `valores`{valor_servico, deducoes, base_calculo, aliquota_iss, valor_iss, valor_liquido}, `retencoes`{irrf, inss, csll, pis, cofins, iss}.
- **boleto**: `beneficiario`{nome, cnpj_cpf}, `pagador`{nome, cnpj_cpf}, `valor_documento`, `data_vencimento`, `data_documento`, `nosso_numero`, `numero_documento`, `linha_digitavel`, `codigo_barras`.
- **recibo**: `numero`, `data`, `pagador`{nome, cnpj_cpf}, `recebedor`{nome, cnpj_cpf}, `valor`, `referente_a`.
- **comprovante_pagamento**: `tipo` (enum: pix|ted|doc|boleto|outro|null), `data`, `pagador`{nome, cnpj_cpf}, `recebedor`{nome, cnpj_cpf}, `valor`, `identificador` (end-to-end/autenticação), `instituicao`.
- **outro**: `descricao` (string|null), `valores_identificados`[]{rotulo, valor}, `raw_text` (required) — the never-blocks generic fallback.

All amounts are `["number","null"]` (R1: no bounds). All strings are `["string","null"]` unless required. Item/list arrays are `{"type":"array","items":{$ref}}`. Every object has `additionalProperties:false`.

**Rationale.** Design §10.3 names exactly these types and §10.1 shows the DANFE field inventory the flat extraction threw away. Mirroring the standards (not inventing) means the transcriber's prompt and the mappers (EXTRACT-005) can rely on stable field names. Amounts are nullable numbers so "absent" is `null`, never a `0` sentinel (spec edge case).

**Alternatives considered.** A single mega-schema with `oneOf` on `doc_type` — rejected: `oneOf` is outside the R1 subset and a per-type registry is what FR-003/FR-004 ask for (add a type = add a file). Storing amounts as strings to preserve `R$ 1.234,56` — rejected here: this is the *typed* contract; raw-string preservation is a transcriber concern, and the existing flat contract already accepts both — out of scope for the schema shape (numbers are the typed target; `raw_text` preserves verbatim page text).

## R4 — `comprovante_pagamento` canonical key + aliases

**Decision.** Canonical registry key = `comprovante_pagamento` (the issue's name). The registry's `ALIASES` maps the existing flat-taxonomy values onto it and onto the others: `comprovante`→`comprovante_pagamento`, `payment_proof`→`comprovante_pagamento`, `nf-e`/`nfe`/`danfe`/`invoice`→`danfe`, `nfs-e`/`nfse`→`nfse`, `boleto`→`boleto`, `recibo`→`recibo`. Unknown/`outro`/`other`/`None`→`outro`. The current flat `record-classification` contract is untouched (FR-011).

**Rationale.** Design §10.3 + the existing `papel_artefato ∈ invoice|nfse|boleto|payment_proof|other` and `tipo_documento ∈ NF-e|DANFE|boleto|recibo|comprovante|outro` taxonomy (classify-doc-page SKILL.md). Recording aliases now lets EXTRACT-004's adapter map old→new without re-deciding the taxonomy.

## R5 — `SCHEMA_VERSION`

**Decision.** `SCHEMA_VERSION = "1"` (string), defined once in `registry.py` and embedded into each schema's required `schema_version` single-value enum (`["1"]`) so a payload self-declares both its type and contract version. Bump on any breaking change.

**Rationale.** FR-008 / Assumption A6 — downstream coexistence of legacy flat rows and new typed rows keys off this; a string keeps it human-stable and future-proof (e.g. `"1.1"`).

## R6 — Test runner / placement

**Decision.** Tests live in `tools/doc-transcribe/tests/` (stdlib `unittest`), run with `python -m unittest discover -s tools/doc-transcribe/tests -t tools/doc-transcribe` (documented in quickstart). They do NOT go in `scripts/tests` (that dir is the analysis suite and would couple the reusable module to the app). The module is import-safe with no third-party deps so CI/`uv` can run it directly.

**Rationale.** Keeps the module self-contained/extractable (design §11.6) while still satisfying the issue's "unit tests" acceptance. The existing `pnpm test:py` targets `scripts/tests`; this module's tests are a separate, documented invocation (and can be wired into CI in a follow-up if desired — out of scope for this contract issue).
