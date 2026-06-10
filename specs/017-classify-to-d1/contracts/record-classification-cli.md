# Contract: `record-classification` CLI command

Part of the analysis CLI (`python -m analysis …`, run from `scripts/`). The per-page write point
that replaces the `<image>.classify.json` file. Called by the `classify-doc-page` skill once per
page after it reads the image.

## Synopsis

```bash
python -m analysis record-classification \
  --attachment-id <attachment_id> \
  --page <page_label> \
  [--page-index <n>] \
  [--json '<json>' | --json - ] \
  [--remote]
```

- `--attachment-id` (required): the attachment the page belongs to (from the work plan's
  `representative_attachment_id`).
- `--page` (required): the page label (from the plan page's `page_label`, e.g. `p1`, `page2`).
- `--page-index` (optional): the 0-based page index (from the plan page's `page_index`); stored for
  reference.
- `--json` (optional): the extraction as a JSON string. If omitted or `-`, the JSON is read from
  **stdin** (the skill pipes a heredoc — robust against quoting/unicode). The JSON is **either** the
  full fields object **or** `{ "error": "<reason>" }`.
- `--remote` (optional): write the production D1 (default: local Miniflare).

## Behavior

1. Parse the JSON (from `--json` or stdin). On invalid JSON → exit non-zero with an actionable
   stderr message.
2. **Validate** against the frozen page-field contract (`validate_page_fields`): exact key set,
   `papel_artefato` ∈ the allowed set, `tipo_documento`/string fields are string-or-null, amount
   fields are number/currency-string/null; **or** the single-key `{"error": "<non-empty string>"}`
   alternative. On violation → exit non-zero with the specific reason (so the skill corrects and
   re-records). (FR-003, SC-006.)
3. **Upsert** one `page_classifications` row keyed by `det_id("page_classification", attachment_id,
   page_label)` via `d1.upsert_tables` (`INSERT OR REPLACE`). A fields object sets `response` (JSON)
   and leaves `error` NULL; an error result sets `error` and leaves `response` NULL. (FR-001, FR-002.)
4. Print a one-line confirmation (`Recorded classification for <attachment_id> <page_label>.`).

## Idempotency

Re-recording the same (attachment_id, page_label) replaces the prior row (same deterministic id) —
exactly one row per page, latest wins (SC-004). No accumulation.

## Exit codes

- `0` — recorded successfully (fields or error result).
- non-zero — invalid JSON or contract violation (message on stderr); nothing written.

## Examples

```bash
# fields object via stdin (how the skill calls it)
cd scripts && uv run python -m analysis record-classification \
  --attachment-id "$AID" --page p1 --page-index 0 <<'JSON'
{ "papel_artefato": "invoice", "tipo_documento": "DANFE", "valor_total": 617.25,
  "valor_liquido": null, "valor_pago": null, "cnpj_emitente": "12.345.678/0001-90",
  "nome_emitente": "ACME LTDA", "data_emissao": "05/12/2025", "numero_documento": "123",
  "descricao_servico": "Manutenção" }
JSON

# error result
cd scripts && uv run python -m analysis record-classification \
  --attachment-id "$AID" --page p2 --json '{"error":"page is blank/illegible"}'
```

## Notes

- `record-classification` is the **only** new writer; it writes to the staging table, never to
  `attachment_analyses` (the merge owns that). It does not stamp `classified_at` (the merge does).
- This is the validation point — the former PostToolUse `validate_classify.py` hook is removed since
  the skill no longer writes a file.
