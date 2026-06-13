"""Typed document-extraction schema registry + stdlib validator (EXTRACT-001).

The portable, project-agnostic contract layer for "image of a Brazilian fiscal
document → typed JSON". Defines a JSON Schema per document type, a type→schema
registry (with an ``outro`` fallback + alias map), and a stdlib-only validator —
no transcriber, no mappers, no persistence, no UI, no third-party dependency.

See README.md for the full contract documentation.
"""

from __future__ import annotations

from .registry import (
    ALIASES,
    DOC_TYPES,
    SCHEMA_VERSION,
    canonical_type,
    load_schema,
    schema_for,
    supported_types,
)
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
]
