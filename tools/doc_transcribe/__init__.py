"""Typed document-extraction contract + vision transcriber (EXTRACT-001 + EXTRACT-002).

The portable, project-agnostic layer for "image of a Brazilian fiscal document → typed JSON":

- EXTRACT-001 — a JSON Schema per document type, a type→schema registry (with an ``outro`` fallback +
  alias map), and a stdlib-only validator.
- EXTRACT-002 — ``transcribe(image, doc_type="auto")`` (library + ``python -m doc_transcribe`` CLI),
  validating the model's typed JSON above a pluggable :class:`Backend` (``cli`` default, ``api``
  optional). Importing this package does NOT import ``anthropic`` (the ``api`` backend imports it
  lazily); the ``cli`` backend needs no API key.

No mappers, no persistence, no UI; zero imports from ``scripts/analysis``. See README.md for the
full documentation.
"""

from __future__ import annotations

from .backends import ApiBackend, Backend, CliBackend, TranscribeError, extract_json
from .registry import (
    ALIASES,
    DOC_TYPES,
    SCHEMA_VERSION,
    canonical_type,
    load_schema,
    schema_for,
    supported_types,
)
from .transcribe import transcribe
from .validator import validate, validate_transcription

__all__ = [
    "SCHEMA_VERSION",
    "DOC_TYPES",
    "ALIASES",
    "canonical_type",
    "load_schema",
    "schema_for",
    "supported_types",
    "validate",
    "validate_transcription",
    "transcribe",
    "Backend",
    "CliBackend",
    "ApiBackend",
    "TranscribeError",
    "extract_json",
]
