# Contract: Extractions file `<period>.extractions.json`

Produced by the `analyze-docs` agent; consumed by `apply-extractions`.

## Shape

A JSON object mapping a page `path` (exactly the `pages[].path` from the manifest) to ONE of:

- a **fields object** conforming to `page-extraction-fields.md`, or
- an **error object** `{ "error": "<reason string>" }`.

```jsonc
{
    "../data/scrape/2025-12/<id>_p1.jpg": {
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
    },
    "../data/scrape/2025-12/<id>_p2.jpg": { "error": "page illegible" },
}
```

## Invariants

- Each value is EITHER a fields object OR an error object — never both, never partial+error.
- Keys are exact manifest `path` strings. Extra keys not in the manifest are ignored by `apply`.
- A manifest page **missing** from this file is treated by `apply` as a per-page error
  (`"no extraction for page"`); it does not abort the document.
- Absent fields are `null`; the agent MUST NOT fabricate values (FR-011).

## Consumer behavior (`apply-extractions`, via `FileExtractionProvider`)

For each representative page `path`:

- fields object → `(parsed_fields, None)` → becomes a `page_extraction` record with `response` set
  and `artifact_role = _map_artifact_role(parsed_fields)`.
- error object / missing → `(None, reason)` → record gets `parse_error = reason` (and `response`
  null), mirroring the current per-page failure handling.

A document with no usable page → document-level `error = "no page produced a parseable response"`,
exactly as today.
