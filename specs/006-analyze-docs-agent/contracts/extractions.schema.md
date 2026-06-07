# Contract: Per-page classification file `<image-stem>.classify.json`

> **Evolution note:** this contract originally specified a single
> `<period>.extractions.json` map written by the `analyze-docs` agent. The implementation moved to
> **one classification file per page image**, written by the `classify-doc-page` skill next to its
> image, and read by `apply-extractions` via `FileExtractionProvider`. The per-page values and
> error semantics are unchanged; only the file layout (one-per-image instead of one-per-period) and
> the producer (a skill instead of the agent) changed.

Produced by the **`classify-doc-page`** skill (one per page image); consumed by `apply-extractions`.

## Location & naming

Written next to the page image, replacing the image extension with `.classify.json`:
`…/<id>_p1.png` → `…/<id>_p1.classify.json` (see `extractions.classify_path_for`).

## Shape

Each file is a single JSON object that is ONE of:

- a **fields object** conforming to `page-extraction-fields.md`, or
- an **error object** `{ "error": "<reason string>" }`.

```jsonc
// <id>_p1.classify.json
{
    "papel_artefato": "invoice",
    "tipo_documento": "NF-e",
    "valor_total": 617.25,
    "valor_liquido": null,
    "valor_pago": null,
    "cnpj_emitente": "12.345.678/0001-90",
    "nome_emitente": "ACME LTDA",
    "data_emissao": "03/12/2025",
    "numero_documento": "12345",
    "descricao_servico": "Serviço de limpeza",
}
```

```jsonc
// <id>_p2.classify.json
{ "error": "page illegible" }
```

## Invariants

- Each file is EITHER a fields object OR an error object — never both, never partial+error.
- Absent fields are `null`; the producer MUST NOT fabricate values (FR-011).
- A manifest page whose `.classify.json` is **missing** is treated by `apply` as a per-page error
  (`"no classification for page (run classify-doc-page)"`); it does not abort the document.

## Consumer behavior (`apply-extractions`, via `FileExtractionProvider`)

For each representative page, the provider resolves the sibling `.classify.json` and returns:

- fields object → `(parsed_fields, None)` → becomes a `page_extraction` record with `response` set
  and `artifact_role = _map_artifact_role(parsed_fields)`.
- error object / missing / unreadable → `(None, reason)` → record gets `parse_error = reason` (and
  `response` null), mirroring the per-page failure handling.

A document with no usable page → document-level `error = "no page produced a parseable response"`,
exactly as before.
