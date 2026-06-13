# Phase 1 Data Model: Vision transcriber (EXTRACT-002)

No persisted entities (no D1/R2, no schema, no migration). The "data" here is the in-memory result
shape and the backend seam.

## Entity: Transcription result (a `dict`)

The return value of `transcribe()` and the JSON printed by the CLI.

| Key             | Type                     | Required | Notes |
| --------------- | ------------------------ | -------- | ----- |
| `doc_type`      | `str`                    | yes      | A canonical EXTRACT-001 type (`danfe`/`nfse`/`boleto`/`recibo`/`comprovante_pagamento`/`outro`). Authoritative: from `canonical_type` (forced type) or model detection (`auto`), never a raw model string. |
| `schema_version`| `str`                    | yes      | `registry.SCHEMA_VERSION` (currently `"1"`). Stamped by the transcriber; a model-echoed version is ignored. |
| `fields`        | `dict`                   | yes      | The full EXTRACT-001-conformant object for `doc_type` — carries its own `doc_type`/`schema_version`/`raw_text` (the evidence floor, FR-009) + the type-specific blocks. This is exactly what `validate_transcription(fields, doc_type)` validates. |
| `parse_errors`  | `list[str]`              | no       | Present **only** when non-empty. Located validation-error strings from the validator, or a single extraction-failure message when the backend returned non-JSON. Its presence means the typed shape did not fully validate; the (best-effort) `fields` is still returned. |

**Validation rules**:
- `fields` is validated with `validate_transcription(fields, doc_type)`; the returned error list becomes
  `parse_errors` (omitted when empty).
- Before validating, the transcriber sets `fields["doc_type"] = doc_type` and
  `fields["schema_version"] = SCHEMA_VERSION` so the envelope is always consistent with the authoritative
  result (clarify Q2, FR-011).
- A non-dict / unparseable backend response yields `fields = {"doc_type": "outro", "schema_version":
  SCHEMA_VERSION, "raw_text": <raw backend text>}` and `parse_errors = ["backend returned no parseable
  JSON"]` (edge cases, SC-005). This `outro` object validates clean against the `outro` schema, so the
  contract still holds.

## Entity: Backend (protocol)

The swappable model-call seam. Knows nothing about validation, the registry, or persistence.

```python
class Backend(Protocol):
    def transcribe_to_json(
        self, *, image_bytes: bytes, media_type: str, schema: dict, instruction: str
    ) -> str: ...
```

| Implementation | Selector  | Dependency / auth | Behavior |
| -------------- | --------- | ----------------- | -------- |
| `CliBackend`   | `"cli"` (default) | `claude` binary on PATH; no SDK, no key | Writes the image to a temp file (or uses the given path), runs `claude -p --output-format text --model <model> --add-dir <dir> "<instruction>"` in a subprocess, returns stdout. |
| `ApiBackend`   | `"api"`   | `anthropic` SDK (optional extra) + `ANTHROPIC_API_KEY` | Lazily imports `anthropic`, builds one non-streaming `messages.create` with an image block + `output_config.format` json_schema=`schema`, returns the response text. Model default `claude-opus-4-8`. |

`schema` is the resolved type's EXTRACT-001 JSON Schema (used as the wire `json_schema` by `api`, and
embedded into the instruction by `cli`). `instruction` is the shared per-type transcription prompt.

## Entity: Document type

One of the six EXTRACT-001 canonical types, resolved via `registry.canonical_type` / `schema_for`.
`"auto"` is a sentinel meaning "no caller-forced type; the model detects it". Reused from EXTRACT-001 —
no new definition.

## Errors

- `TranscribeError(RuntimeError)` — raised at **call time** (never import) for: `api` backend selected
  without the `anthropic` SDK importable; `api` backend selected without `ANTHROPIC_API_KEY`; `cli`
  backend selected without the `claude` binary on PATH; unreadable/missing image file; unknown `backend`
  value. Carries an actionable message.
