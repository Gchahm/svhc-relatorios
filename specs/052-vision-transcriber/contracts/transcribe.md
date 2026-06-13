# Contract: `transcribe()` library function, CLI, and Backend seam (EXTRACT-002)

This is a Python module contract (no HTTP/REST surface — the module is offline tooling).

## Library function

```python
def transcribe(
    image: str | bytes | os.PathLike,
    doc_type: str = "auto",
    *,
    backend: str = "cli",
    model: str | None = None,
    backend_impl: "Backend | None" = None,   # test/override seam; built from `backend` when None
) -> dict:
    """Transcribe a fiscal-document page image into validated typed JSON.

    Returns {"doc_type", "schema_version", "fields"[, "parse_errors"]}.
    Never raises on a bad *model response* (records parse_errors); raises
    TranscribeError on a config/usage error (bad backend, missing dep/key, unreadable image).
    """
```

- `image`: a path (str / PathLike) to an image file, or raw image bytes.
- `doc_type`: `"auto"` (model detects) or any EXTRACT-001 type / alias (forced, resolved via
  `canonical_type`).
- `backend`: `"cli"` (default) or `"api"`. Unknown → `TranscribeError`.
- `model`: optional model override. `api` default `claude-opus-4-8`; `cli` default = the session's
  configured model (passed as `--model opus` only when `model` is given).
- `backend_impl`: inject a `Backend` (used by tests / advanced callers); when `None`, built from
  `backend` + `model`.

**Behavior contract**:
1. Resolve `dt = canonical_type(doc_type)` when `doc_type != "auto"`, else `dt` is decided after the
   backend returns (from the model's reported `doc_type`, run through `canonical_type`, default `outro`).
2. `schema = schema_for(dt or "auto"→outro-instructional)`; build `instruction` from `prompts.py`.
3. Call `backend_impl.transcribe_to_json(image_bytes, media_type, schema, instruction)`.
4. Extract JSON (`extract_json`). If `None` → return `outro` best-effort result with a `parse_errors`
   entry. Else `fields = parsed`.
5. For `auto`, set `dt = canonical_type(fields.get("doc_type"))`; reload `schema_for(dt)` if it changed.
6. Stamp `fields["doc_type"] = dt`, `fields["schema_version"] = SCHEMA_VERSION`.
7. `errs = validate_transcription(fields, dt)`. Return `{"doc_type": dt, "schema_version":
   SCHEMA_VERSION, "fields": fields}` and add `"parse_errors": errs` iff `errs`.

## CLI

```
python -m doc_transcribe --image <path> [--type auto] [--backend cli|api] [--model <id>]
```

- Prints exactly one JSON object (the `transcribe()` result) to **stdout**, exit `0`.
- On a config/usage error (missing/unreadable image, missing dep/key, bad backend): prints a readable
  message to **stderr**, exit non-zero. (A bad model response is NOT an error — it prints the result
  with `parse_errors` and exits 0.)
- `--type` maps to `doc_type` (default `auto`); `--backend` to `backend` (default `cli`); `--model` to
  `model`.

## Backend protocol

```python
class Backend(Protocol):
    def transcribe_to_json(
        self, *, image_bytes: bytes, media_type: str, schema: dict, instruction: str
    ) -> str: ...
```

Returns the raw JSON text the model produced (the module parses + validates above it). Implementations:
`CliBackend(model: str | None)`, `ApiBackend(model: str = "claude-opus-4-8")`.

## Invariants (testable)

- **INV-1** (FR-003): the returned `fields` has been validated with `validate_transcription`; any errors
  are in `parse_errors`.
- **INV-2** (FR-007, SC-002): `import doc_transcribe` and a `cli`-backend `transcribe()` succeed with
  `anthropic` not importable and `ANTHROPIC_API_KEY` unset.
- **INV-3** (FR-006, SC-003): the `api` backend's request carries the resolved type's schema as
  `output_config.format` json_schema and an image block.
- **INV-4** (FR-011): `result["doc_type"]` is always a canonical EXTRACT-001 type and
  `result["schema_version"] == SCHEMA_VERSION`, regardless of what the model echoed.
- **INV-5** (SC-005): a non-JSON / invalid backend response produces a result (with `parse_errors`),
  never an unhandled exception.
- **INV-6** (FR-010): no module file imports `scripts.analysis`; no new mandatory dependency.
- **INV-7** (FR-007): selecting `api` without the SDK / without the key raises `TranscribeError` at call
  time with an actionable message (not at import).
