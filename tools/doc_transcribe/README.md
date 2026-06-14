# `doc_transcribe` — typed document extraction + vision transcriber (EXTRACT-001 + EXTRACT-002)

The portable, project-agnostic layer for "image of a Brazilian fiscal document → typed JSON":

- **EXTRACT-001 (the contract):** a JSON Schema per document type, a type→schema registry, and a stdlib-only validator. The foundation every later EXTRACT piece builds on.
- **EXTRACT-002 (the transcriber):** `transcribe(image, doc_type="auto")` plus a `python -m doc_transcribe` CLI that turns a page image into validated typed JSON above a pluggable backend. See [The transcriber](#the-transcriber-extract-002) below.

> **Self-contained by design.** This module has **zero imports from `scripts/analysis`** (design `docs/features/false-positive-triage-agent.md` §11.6). The schemas are national-standard layouts, not SVHC-specific, so the whole module is extractable to its own repo with no untangling. The only contract between this module and the app is the typed JSON.

## What this is / is NOT

- **IS**: six JSON Schemas (`danfe`, `nfse`, `boleto`, `recibo`, `comprovante_pagamento`, `outro`), a registry with an `outro` fallback + alias map, a stdlib-only validator, and a `SCHEMA_VERSION` constant.
- **IS NOT**: a transcriber/vision call (EXTRACT-002/003), the deterministic reconciliation mappers (EXTRACT-005), a persistence / `record-classification` change (EXTRACT-004), or a UI change (EXTRACT-006). It changes no DB schema, runs no migration, and adds **no** pip/npm dependency.

## Document types & schemas

Each schema mirrors the real Brazilian layout for its type (NF-e/DANFSe are SEFAZ national standards). Every typed payload carries a common envelope — required `doc_type` (single-value enum identifying the type), `schema_version` (== `SCHEMA_VERSION`), and `raw_text` (the full verbatim page text, the evidence floor) — then type-specific blocks:

| Type                    | Key blocks (see `schemas/<type>.json`)                                                                                                                                                                                                                                                                 |
| ----------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| `danfe`                 | `chave_acesso`, `numero`, `serie`, `natureza_operacao`, `data_emissao`, `emitente`{nome,cnpj,ie,endereco}, `destinatario`, `itens[]`{descricao,ncm,cfop,quantidade,valor_unitario,valor_total}, `totais`{valor_produtos,base_calculo_icms,valor_icms,valor_frete,valor_total_nota=vNF}, `duplicatas[]` |
| `nfse`                  | `numero`, `codigo_verificacao`, `data_emissao`, `prestador`{nome,cnpj,im}, `tomador`, `discriminacao_servico`, `valores`{valor_servico,deducoes,base_calculo,aliquota_iss,valor_iss,valor_liquido}, `retencoes`{irrf,inss,csll,pis,cofins,iss}                                                         |
| `boleto`                | `beneficiario`, `pagador`, `valor_documento`, `data_vencimento`, `data_documento`, `nosso_numero`, `numero_documento`, `linha_digitavel`, `codigo_barras`                                                                                                                                              |
| `recibo`                | `numero`, `data`, `pagador`, `recebedor`, `valor`, `referente_a`                                                                                                                                                                                                                                       |
| `comprovante_pagamento` | `tipo` (pix\|ted\|doc\|boleto\|outro\|null), `data`, `pagador`, `recebedor` (favorecido), `valor`, `identificador` (E2E/autenticação), `instituicao`                                                                                                                                                   |
| `outro`                 | generic fallback — required `raw_text` only, plus optional `descricao` + `valores_identificados[]`{rotulo,valor}. **Never blocks.**                                                                                                                                                                    |

All amounts are `number | null` (absent ⇒ `null`, never a `0` sentinel). All non-required scalars are nullable.

### Adding a new type

Drop `schemas/<key>.json` in, add `<key>` to `DOC_TYPES` (and any aliases to `ALIASES`) in `registry.py`, add an `examples/<key>.json` fixture. Nothing in the validator or the existing schemas changes.

## Registry API (`registry.py`)

- `SCHEMA_VERSION: str` — contract version (`"1"`). Bumped (e.g. `"1.1"`) on any breaking change. Downstream uses it to distinguish typed rows from legacy flat rows.
- `DOC_TYPES: tuple[str, ...]` — the six canonical keys.
- `ALIASES: dict[str, str]` — flat-taxonomy values + spelling variants → canonical key (matched case/space/underscore/hyphen-insensitively). E.g. `comprovante`/`payment_proof` → `comprovante_pagamento`, `NF-e`/`nfe`/`invoice` → `danfe`, `nfs-e` → `nfse`. Lets the EXTRACT-004 adapter map the existing `papel_artefato`/`tipo_documento` taxonomy onto these without re-deciding it. (The current flat `record-classification` contract is untouched here.)
- `canonical_type(doc_type) -> str` — the canonical key a raw type resolves to, or `"outro"`.
- `schema_for(doc_type) -> dict` — the schema for a (possibly aliased/unknown/None) type; unknown → `outro`. **Never raises.**
- `load_schema(doc_type) -> dict` — load by EXACT canonical key (cached); raises `KeyError` for a non-`DOC_TYPES` key (programmer error).
- `supported_types() -> tuple[str, ...]` — `DOC_TYPES`.

## Validator API (`validator.py`)

- `validate(payload, schema) -> list[str]` — stdlib-only validation against a schema. Returns located, human-readable error strings (`"$.path: reason"`); an **empty list means valid**. Does not raise on an invalid _payload_; raises `ValueError` only on a malformed _schema_.
- `validate_transcription(payload, doc_type) -> list[str]` — `validate(payload, schema_for(doc_type))`.

It implements **exactly** the structured-output subset the schemas use: `type` (incl. `["x","null"]` unions), `enum`, `required`, `properties` + `additionalProperties:false`, `items`, `anyOf`, and `$ref` into `$defs`. Notable rules: a JSON `true`/`false` is **not** a `number`; `int`/`float` both satisfy `number`; a non-object payload against an `object` schema yields one top-level error (no crash). Error paths use `$` (root), `.field`, `[i]`.

## Structured-output subset (why it matters)

These schemas double as the EXTRACT-002 `api` backend's wire `output_config` schema. The Anthropic structured-output feature supports objects/arrays/enums/`anyOf`/`$ref` and requires `additionalProperties:false`, but **strips/rejects** numeric/length/pattern bounds and recursion. So every schema MUST stay within that subset: no `minimum`/`maximum`/`min*`/`max*`/`pattern`/`format`/`if`/`then`/`else`/`not`/`allOf`/`oneOf`, every object declares `additionalProperties:false`, every `$ref` is a local `#/$defs/<name>` and the `$defs` graph is acyclic (no recursion). `tests/test_subset_constraints.py` enforces this automatically over every registered schema, so a future schema edit that breaks the subset fails CI rather than silently changing meaning at the wire.

## The transcriber (EXTRACT-002)

`transcribe()` turns a fiscal-document page image into validated typed JSON conforming to the EXTRACT-001 contract. The model call sits behind a **pluggable backend**; **schema validation lives above the backend**, so the typed-JSON guarantee never depends on which backend ran.

```python
from doc_transcribe import transcribe

result = transcribe("page.png")                       # doc_type="auto", cli backend (default)
result = transcribe("page.png", doc_type="recibo")    # force a type
result = transcribe("page.png", backend="api")         # Anthropic API backend (optional)
```

```bash
python -m doc_transcribe --image page.png [--type auto] [--backend cli|api] [--model <id>]
```

### Result envelope

```jsonc
{
    "doc_type": "recibo", // canonical EXTRACT-001 type (authoritative)
    "schema_version": "1", // == registry SCHEMA_VERSION (a model-echoed version is ignored)
    "fields": {
        /* the full EXTRACT-001-conformant object for the type, incl. raw_text */
    },
    "parse_errors": ["$.valor: ..."], // present ONLY when validation found problems
}
```

`fields` is exactly what `validate_transcription(fields, doc_type)` validates; the transcriber stamps the authoritative canonical `doc_type`/`schema_version` onto it before validating (so a model echoing a wrong type/version can't produce an inconsistent result). A non-JSON / unparseable model response is surfaced as an `outro` best-effort object plus a `parse_errors` entry — `transcribe()` **never raises on a bad model response**; it raises `TranscribeError` only on a config/usage error (bad backend, missing optional dep/key, unreadable image).

### Backends

| Backend | Selector          | Needs                                     | Behavior                                                                                                                                                                                                                                                                        |
| ------- | ----------------- | ----------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `cli`   | `"cli"` (default) | the `claude` binary on PATH (Claude Code) | Shells out to `claude -p` in its own subprocess (prompt via stdin; image read via `--add-dir`). **No `anthropic` SDK, no `ANTHROPIC_API_KEY`.** Keeps page images out of any orchestrator's context. The CLI doesn't enforce a schema — the module parses + validates above it. |
| `api`   | `"api"`           | the `anthropic` SDK (optional) + a key    | One non-streaming `messages.create` with the schema in the **prompt** (NOT `output_config.format` — wire-enforced structured output caps optional params at 24, which the rich typed schemas exceed) + an image block; the JSON is parsed + validated above the backend, like `cli`. Default model `claude-haiku-4-5-20251001` (override with `--model`), adaptive thinking. Lazily imports `anthropic`, so the package imports fine without it. |

Transcribe-only: the transcriber records what the page shows and does **not** compute reconciliation values (that is EXTRACT-003). It is **not** wired into `record-classification`/D1 (that adapter is EXTRACT-004). The `anthropic` SDK is an **optional extra** — `import doc_transcribe` and the `cli` backend work with it absent.

## Run the tests

From the repo root (Python via `uv`):

```bash
uv run python -m unittest discover -s tools/doc_transcribe/tests -t tools
```

Covers: registry resolution/fallback/aliases/`SCHEMA_VERSION`, validator positive + every negative category (missing required, wrong type, unknown key, out-of-enum, non-object root, bool-not-number, array items, anyOf), each example fixture validating against its schema (incl. the real corpus values — DANFE `000006227`/vNF=2790,00, NFS-e R$320), and the subset checker.

## Layout

```
tools/doc_transcribe/
├── __init__.py            # public API re-exports (registry + validator + transcribe)
├── registry.py            # SCHEMA_VERSION, DOC_TYPES, ALIASES, schema_for/load_schema/...
├── validator.py           # stdlib validate() / validate_transcription()
├── transcribe.py          # transcribe() — result assembly, type resolution, validate-above-backend
├── backends.py            # Backend protocol + CliBackend (claude -p) + ApiBackend (anthropic SDK) + extract_json
├── prompts.py             # shared per-type transcription instruction
├── __main__.py            # CLI: python -m doc_transcribe --image <path> ...
├── schemas/<type>.json    # the six JSON Schemas
├── examples/<type>.json    # real/representative example transcriptions (test fixtures)
└── tests/                  # unittest suite (registry/validator/subset + transcribe/backends/cli)
```

> **Directory name.** The design doc writes `tools/doc-transcribe/`; the actual directory is `tools/doc_transcribe/` (underscore) so it is a valid importable Python package. The intent and placement are unchanged.
