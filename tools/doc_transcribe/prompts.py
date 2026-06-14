"""Shared transcription instruction builder for the EXTRACT-002 vision transcriber.

Both backends (``cli`` and ``api``) feed the model the SAME instruction: transcribe everything on the
page into the typed JSON schema for the (detected or forced) document type, including the full verbatim
``raw_text`` evidence floor, and emit ONLY the JSON object. The transcriber is transcribe-only — the
model records what the page shows and does NOT compute or derive reconciliation values (that is
EXTRACT-003). Stdlib-only; zero imports from ``scripts/analysis``.
"""

from __future__ import annotations

import json

_TRANSCRIBE_ONLY = (
    "Transcribe only. Record exactly what is printed on the page — do not compute totals, "
    "reconcile amounts, infer values that are not shown, or decide which number is 'the' total. "
    "Absent fields are null."
)


def build_instruction(schema: dict, doc_type: str) -> str:
    """Build the transcription instruction for ``doc_type`` against its JSON Schema.

    ``doc_type`` is the resolved canonical type, or ``"auto"`` when the model must detect the type.
    The instruction names the schema verbatim so the model fills the typed shape; the module validates
    the returned JSON against this same schema above the backend (the ``cli`` backend does not enforce
    it at the wire, which is exactly why our own validation layer is mandatory).
    """
    schema_text = json.dumps(schema, ensure_ascii=False, indent=2)
    if doc_type == "auto":
        type_line = (
            "First identify the Brazilian fiscal-document type. The schema below is an 'anyOf' over "
            "all supported types; choose the branch that matches the document, set the JSON "
            "'doc_type' field to that type, and fill that branch's structured fields — do NOT return "
            "only raw_text. Use 'outro' ONLY when the document is genuinely none of the specific types."
        )
    else:
        type_line = f"The document type is '{doc_type}'. Set the JSON 'doc_type' field to '{doc_type}'."

    return (
        "You are transcribing an image of a Brazilian fiscal document into typed JSON.\n"
        f"{type_line}\n"
        "Read the image, then transcribe its full content into a single JSON object that conforms "
        "to this JSON Schema:\n\n"
        f"{schema_text}\n\n"
        "Always include the full verbatim page text in the 'raw_text' field.\n"
        f"{_TRANSCRIBE_ONLY}\n"
        "Output ONLY the JSON object — no prose, no explanation, no markdown fences."
    )
