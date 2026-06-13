"""Shared test helpers: load committed example fixtures + walk schema nodes."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Iterator

_MODULE_ROOT = Path(__file__).resolve().parent.parent
_EXAMPLES_DIR = _MODULE_ROOT / "examples"


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
