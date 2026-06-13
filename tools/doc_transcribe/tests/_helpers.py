"""Shared test helpers: load committed example fixtures + walk schema nodes."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Iterator

_MODULE_ROOT = Path(__file__).resolve().parent.parent
_EXAMPLES_DIR = _MODULE_ROOT / "examples"

# A minimal valid 1x1 PNG (so tests can pass real image bytes without a fixture file).
SAMPLE_PNG = bytes.fromhex(
    "89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c4"
    "890000000a49444154789c6360000002000154a24f8b0000000049454e44ae426082"
)


class FakeBackend:
    """A ``Backend`` test double: returns a canned JSON string and records its call args.

    No subprocess, no network — drives the transcribe()/CLI result-assembly paths deterministically.
    """

    def __init__(self, canned_json: str) -> None:
        self.canned_json = canned_json
        self.calls: list[dict] = []

    def transcribe_to_json(self, *, image_bytes: bytes, media_type: str, schema: dict, instruction: str) -> str:
        self.calls.append(
            {"image_bytes": image_bytes, "media_type": media_type, "schema": schema, "instruction": instruction}
        )
        return self.canned_json


def load_example(doc_type: str) -> dict:
    with (_EXAMPLES_DIR / f"{doc_type}.json").open(encoding="utf-8") as fh:
        return json.load(fh)


def iter_schema_nodes(schema: dict) -> Iterator[dict]:
    """Yield every schema-object node (dicts) reachable in a schema, including
    the root, $defs entries, properties, items, and anyOf branches."""
    stack: list[object] = [schema]
    while stack:
        node = stack.pop()
        if isinstance(node, dict):
            yield node
            for value in node.values():
                stack.append(value)
        elif isinstance(node, list):
            stack.extend(node)
