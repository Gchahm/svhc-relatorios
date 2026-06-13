"""Stdlib-only JSON-Schema validator for the typed document-extraction contract.

Implements EXACTLY the structured-output subset the schemas in this module use
(see README.md / the EXTRACT-001 spec): ``type`` (including ``["x","null"]``
nullable unions), ``enum``, ``required``, ``properties`` + ``additionalProperties:
false``, ``items``, ``anyOf``, and ``$ref`` resolution into the root ``$defs``.

It is NOT a full JSON Schema engine: numeric/length/pattern bounds, ``allOf`` /
``oneOf`` / ``not`` / ``if`` and recursion are deliberately unsupported because the
schemas are forbidden from using them (the API structured-output backend would
strip/reject them — see ``tests/test_subset_constraints.py``). This keeps the
validator small and free of any third-party dependency, so the analysis package
and the ``cli`` transcriber backend can both call it.

Public API:
    validate(payload, schema) -> list[str]
    validate_transcription(payload, doc_type) -> list[str]

Both return a list of located, human-readable error strings; an empty list means
the payload is valid. Neither raises on an invalid *payload*; ``validate`` may
raise ValueError only on a malformed *schema* (a programmer error).
"""

from __future__ import annotations

from typing import Any

# Map a JSON Schema primitive type name to the Python types that satisfy it.
# NOTE: bool is intentionally NOT a "number"/"integer" (JSON true/false are only
# "boolean"), and only int satisfies "integer".
_JSON_TYPES = {
    "object": (dict,),
    "array": (list,),
    "string": (str,),
    "boolean": (bool,),
    "null": (type(None),),
}


def _py_matches_json_type(value: Any, json_type: str) -> bool:
    if json_type == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if json_type == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    expected = _JSON_TYPES.get(json_type)
    if expected is None:
        raise ValueError(f"unsupported schema type {json_type!r}")
    # bool is a subclass of int; guard so a bool only matches "boolean".
    if json_type != "boolean" and isinstance(value, bool):
        return bool in expected
    return isinstance(value, expected)


def _resolve_ref(ref: str, root: dict) -> dict:
    if not ref.startswith("#/"):
        raise ValueError(f"unsupported $ref {ref!r} (only local #/... refs allowed)")
    node: Any = root
    for part in ref[2:].split("/"):
        if not isinstance(node, dict) or part not in node:
            raise ValueError(f"unresolvable $ref {ref!r}")
        node = node[part]
    if not isinstance(node, dict):
        raise ValueError(f"$ref {ref!r} does not point at a schema object")
    return node


def _type_names(schema: dict) -> list[str]:
    """Return the declared type(s) as a list, or [] if none declared."""
    t = schema.get("type")
    if t is None:
        return []
    if isinstance(t, str):
        return [t]
    if isinstance(t, list):
        return list(t)
    raise ValueError(f"invalid 'type' value {t!r}")


def _validate(value: Any, schema: dict, root: dict, path: str, errors: list[str], depth: int) -> None:
    if depth > 64:
        raise ValueError("schema nesting too deep (recursion is not allowed in the subset)")

    if "$ref" in schema:
        _validate(value, _resolve_ref(schema["$ref"], root), root, path, errors, depth + 1)
        return

    if "anyOf" in schema:
        branches = schema["anyOf"]
        if not isinstance(branches, list) or not branches:
            raise ValueError(f"{path}: 'anyOf' must be a non-empty list")
        branch_errors: list[list[str]] = []
        for branch in branches:
            sub: list[str] = []
            _validate(value, branch, root, path, sub, depth + 1)
            if not sub:
                return  # matched a branch
            branch_errors.append(sub)
        flat = "; ".join(e for sub in branch_errors for e in sub)
        errors.append(f"{path}: does not match any anyOf branch ({flat})")
        return

    # enum
    if "enum" in schema:
        allowed = schema["enum"]
        if value not in allowed:
            errors.append(f"{path}: {value!r} not in enum {allowed!r}")
            # still fall through to type checks below for a fuller message? No —
            # an enum miss is the salient error; return to avoid noise.
            return

    types = _type_names(schema)
    if types:
        if not any(_py_matches_json_type(value, t) for t in types):
            errors.append(f"{path}: expected {_describe_types(types)}, got {_typename(value)}")
            return  # type is wrong; deeper checks would be misleading

    # object
    if isinstance(value, dict) and ("object" in types or (not types and "properties" in schema)):
        props = schema.get("properties", {})
        required = schema.get("required", [])
        for key in required:
            if key not in value:
                errors.append(f"{path}: missing required field {key!r}")
        additional = schema.get("additionalProperties", True)
        for key, sub_value in value.items():
            child_path = f"{path}.{key}" if path != "$" else f"$.{key}"
            if key in props:
                _validate(sub_value, props[key], root, child_path, errors, depth + 1)
            elif additional is False:
                errors.append(f"{path}: unexpected key {key!r}")
            elif isinstance(additional, dict):
                _validate(sub_value, additional, root, child_path, errors, depth + 1)

    # array
    if isinstance(value, list) and ("array" in types or (not types and "items" in schema)):
        item_schema = schema.get("items")
        if isinstance(item_schema, dict):
            for i, item in enumerate(value):
                _validate(item, item_schema, root, f"{path}[{i}]", errors, depth + 1)


def _typename(value: Any) -> str:
    if isinstance(value, bool):
        return "bool"
    if value is None:
        return "null"
    return type(value).__name__


def _describe_types(types: list[str]) -> str:
    readable = [t if t != "null" else "null" for t in types]
    if len(readable) == 1:
        return readable[0]
    return " or ".join(readable)


def validate(payload: Any, schema: dict) -> list[str]:
    """Validate ``payload`` against ``schema`` (a dict). Returns located error
    strings; an empty list means valid. Raises ValueError only on a malformed
    schema."""
    if not isinstance(schema, dict):
        raise ValueError("schema must be a dict")
    errors: list[str] = []
    _validate(payload, schema, schema, "$", errors, 0)
    return errors


def validate_transcription(payload: Any, doc_type: str | None) -> list[str]:
    """Resolve the schema for ``doc_type`` via the registry, then validate."""
    from .registry import schema_for

    return validate(payload, schema_for(doc_type))
