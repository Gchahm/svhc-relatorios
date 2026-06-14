"""The executable contract gate to the EXTRACT-001 typed-extraction schema (feature 055).

This is the ONE place the analysis *pipeline* reaches into the reusable transcriber library
``tools/doc_transcribe`` — and it does so only at RUNTIME, behind a function call, never at module
import. The analysis *library* (``attachments`` roll-up, ``type_mappers``, the ``page_classifications``
core contract) stays import-clean of ``tools/`` (design §11.6 keeps ``doc_transcribe`` extractable to
its own repo). ``record-classification`` — the runtime contract gate — is exactly the kind of caller
``transcribe()``/``validate_transcription`` are meant to have, so importing it here is the explicit,
contained boundary the issue (#89, EXTRACT-004) asks for ("validate the payload against the EXTRACT-001
schema").

The analysis CLI runs with ``cwd = scripts/``, where ``tools/`` is off ``sys.path``; this module
resolves the repo root the same way ``scripts/common/d1.py`` does (``parents[2]``) and inserts
``<repo>/tools`` so ``import doc_transcribe`` resolves.
"""

from __future__ import annotations

import sys
from pathlib import Path

# Repo layout: scripts/analysis/typed_gate.py -> parents[2] is the repo root (where wrangler.toml and
# tools/ live), mirroring scripts/common/d1.py's _REPO_ROOT resolution.
_TOOLS_DIR = Path(__file__).resolve().parents[2] / "tools"


def _ensure_tools_on_path() -> None:
    """Put <repo>/tools on sys.path (idempotent) so ``import doc_transcribe`` resolves."""
    p = str(_TOOLS_DIR)
    if p not in sys.path:
        sys.path.insert(0, p)


def validate_typed(payload: dict, doc_type) -> list[str]:
    """Validate a typed transcription payload against its EXTRACT-001 schema.

    Delegates to ``doc_transcribe.validate_transcription`` (which resolves the schema for
    ``doc_type`` via the registry — an unknown type falls back to the ``outro`` schema and never
    raises on the type alone). Returns a list of located, human-readable error strings; an empty
    list means the payload conforms. The import is lazy (inside the call) so the analysis package
    imports without ``tools/`` on the path.
    """
    _ensure_tools_on_path()
    from doc_transcribe import validate_transcription  # type: ignore[import-not-found]

    return validate_transcription(payload, doc_type)
