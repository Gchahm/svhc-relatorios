"""``transcribe(image, doc_type="auto") -> typed JSON`` — the EXTRACT-002 vision transcriber.

Turns a fiscal-document page image into validated typed JSON conforming to the EXTRACT-001 contract.
The model call sits behind a pluggable :class:`Backend` (``cli`` default / ``api`` optional); schema
validation lives ABOVE the backend, so the typed-JSON guarantee never depends on which backend ran.

Returns ``{"doc_type", "schema_version", "fields"[, "parse_errors"]}``:

- ``doc_type`` — a canonical EXTRACT-001 type (authoritative: forced type, or model detection for
  ``"auto"``, always run through the registry; ``outro`` fallback).
- ``schema_version`` — the registry ``SCHEMA_VERSION`` (a model-echoed version is ignored).
- ``fields`` — the full EXTRACT-001-conformant object for that type (carries its own
  ``doc_type``/``schema_version``/``raw_text`` + type blocks), exactly what ``validate_transcription``
  validates.
- ``parse_errors`` — present ONLY when non-empty; located validation errors, or a single
  extraction-failure message when the backend returned no parseable JSON.

Transcribe-only: no reconciliation values are computed here (that is EXTRACT-003). Never raises on a bad
*model response* (records ``parse_errors``); raises :class:`TranscribeError` on a config/usage error.
Zero imports from ``scripts/analysis``; no top-level ``anthropic`` import.
"""

from __future__ import annotations

import os

from .backends import ApiBackend, Backend, CliBackend, TranscribeError, extract_json, media_type_for
from .prompts import build_instruction
from .registry import SCHEMA_VERSION, canonical_type, schema_for, union_schema
from .validator import validate_transcription

_NO_JSON_ERROR = "backend returned no parseable JSON"


def _read_image(image: str | bytes | os.PathLike) -> tuple[bytes, str]:
    """Return (image_bytes, media_type) from a path or raw bytes."""
    if isinstance(image, bytes):
        return image, media_type_for(image)
    if isinstance(image, bytearray):
        return bytes(image), media_type_for(bytes(image))
    try:
        with open(image, "rb") as fh:
            data = fh.read()
    except OSError as exc:
        raise TranscribeError(f"could not read image {image!r}: {exc}") from exc
    if not data:
        raise TranscribeError(f"image {image!r} is empty")
    return data, media_type_for(image)


def _make_backend(backend: str, model: str | None) -> Backend:
    if backend == "cli":
        return CliBackend(model)
    if backend == "api":
        return ApiBackend(model) if model else ApiBackend()
    raise TranscribeError(f"unknown backend {backend!r}; expected 'cli' or 'api'")


def _result(doc_type: str, fields: dict, parse_errors: list[str]) -> dict:
    out = {"doc_type": doc_type, "schema_version": SCHEMA_VERSION, "fields": fields}
    if parse_errors:
        out["parse_errors"] = parse_errors
    return out


def transcribe(
    image: str | bytes | os.PathLike,
    doc_type: str = "auto",
    *,
    backend: str = "cli",
    model: str | None = None,
    backend_impl: Backend | None = None,
) -> dict:
    """Transcribe ``image`` into validated typed JSON. See module docstring for the result shape."""
    image_bytes, media_type = _read_image(image)

    forced = doc_type != "auto"
    # For the instruction schema, resolve now. A forced type shows that type's schema. "auto" shows
    # the anyOf UNION of every type's schema, so the model classifies AND fills the matching type's
    # structured fields in one pass (showing only ``outro`` could yield raw_text but never structured
    # fields). Either way we re-resolve from the model's reported ``doc_type`` and validate against
    # that specific type's schema after the backend returns.
    resolved = canonical_type(doc_type) if forced else "auto"
    instruction_schema = schema_for(doc_type) if forced else union_schema()
    instruction = build_instruction(instruction_schema, resolved)

    impl = backend_impl if backend_impl is not None else _make_backend(backend, model)
    raw = impl.transcribe_to_json(
        image_bytes=image_bytes, media_type=media_type, schema=instruction_schema, instruction=instruction
    )

    parsed = extract_json(raw)
    if parsed is None:
        outro = {"doc_type": "outro", "schema_version": SCHEMA_VERSION, "raw_text": raw if isinstance(raw, str) else ""}
        return _result("outro", outro, [_NO_JSON_ERROR])

    fields = parsed
    if forced:
        dt = canonical_type(doc_type)
    else:
        dt = canonical_type(fields.get("doc_type"))

    # Stamp authoritative canonical values onto the envelope so a model echoing a wrong type/version
    # cannot produce an inconsistent result (FR-011).
    fields["doc_type"] = dt
    fields["schema_version"] = SCHEMA_VERSION

    errors = validate_transcription(fields, dt)
    return _result(dt, fields, errors)
