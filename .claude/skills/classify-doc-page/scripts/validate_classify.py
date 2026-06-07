#!/usr/bin/env python3
"""PostToolUse validator for the `classify-doc-page` skill.

Runs after every Write/Edit in the skill. It checks the file the agent just
wrote: if it is the skill's classification output it must (a) follow the
`<image-stem>.classify.json` naming convention and (b) be valid JSON matching the
frozen output contract (either the fields object with exactly the expected keys,
or an `{"error": "<reason>"}` object).

On a violation it exits 2 with a message on stderr — for a PostToolUse hook this
feeds the message back to the model so it can rewrite the file correctly. On
success (or for files this validator does not care about) it exits 0.

Input: the PostToolUse hook JSON on stdin (uses `tool_input.file_path`). For
manual testing, a file path may be passed as the first CLI argument instead.
Stdlib only.
"""

import json
import sys
from pathlib import Path

# The frozen field set (mirrors .claude/skills/classify-doc-page/templates/result.json and
# the page-extraction contract the deterministic pipeline consumes).
REQUIRED_KEYS = {
    "papel_artefato",
    "tipo_documento",
    "valor_total",
    "valor_liquido",
    "valor_pago",
    "cnpj_emitente",
    "nome_emitente",
    "data_emissao",
    "numero_documento",
    "descricao_servico",
}
PAPEL_VALUES = {"invoice", "nfse", "boleto", "payment_proof", "other"}
STRING_OR_NULL = {
    "tipo_documento",
    "cnpj_emitente",
    "nome_emitente",
    "data_emissao",
    "numero_documento",
    "descricao_servico",
}
AMOUNT_KEYS = {"valor_total", "valor_liquido", "valor_pago"}


def _fail(msg: str) -> None:
    """Report a blocking validation error back to the model and stop."""
    sys.stderr.write(f"[classify-doc-page] classify-output validation failed: {msg}\n")
    sys.exit(2)


def _ok(msg: str) -> None:
    print(f"[classify-doc-page] {msg}")
    sys.exit(0)


def _written_path() -> str | None:
    """The path of the file the tool wrote, from CLI arg or the hook stdin JSON."""
    if len(sys.argv) > 1 and sys.argv[1].strip():
        return sys.argv[1].strip()
    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        return None
    tool_input = payload.get("tool_input") or {}
    path = tool_input.get("file_path") or tool_input.get("path")
    return path.strip() if isinstance(path, str) and path.strip() else None


def _validate_fields(obj: dict) -> None:
    keys = set(obj)

    # An error object is the one allowed alternative to the fields object.
    if "error" in keys:
        if keys != {"error"}:
            _fail(f"an error result must be exactly {{\"error\": \"...\"}}, got keys {sorted(keys)}")
        if not isinstance(obj["error"], str) or not obj["error"].strip():
            _fail('"error" must be a non-empty string')
        return

    missing = REQUIRED_KEYS - keys
    extra = keys - REQUIRED_KEYS
    if missing:
        _fail(f"missing required field(s): {sorted(missing)}")
    if extra:
        _fail(f"unexpected field(s) (do not add/rename keys): {sorted(extra)}")

    papel = obj["papel_artefato"]
    if papel not in PAPEL_VALUES:
        _fail(f"papel_artefato must be one of {sorted(PAPEL_VALUES)}, got {papel!r}")

    for k in STRING_OR_NULL:
        v = obj[k]
        if v is not None and not isinstance(v, str):
            _fail(f"{k} must be a string or null, got {type(v).__name__}")

    for k in AMOUNT_KEYS:
        v = obj[k]
        if v is None:
            continue
        # bool is a subclass of int — reject it explicitly.
        if isinstance(v, bool) or not isinstance(v, (int, float, str)):
            _fail(f"{k} must be a number, a currency string, or null, got {type(v).__name__}")


def main() -> None:
    path = _written_path()
    if path is None:
        # Can't determine what was written — don't block on hook plumbing issues.
        sys.exit(0)

    p = Path(path)
    name = p.name

    # Only JSON outputs are this skill's concern; ignore anything else.
    if not name.endswith(".json"):
        sys.exit(0)

    # Naming convention: the classification result must be `<stem>.classify.json`.
    if not name.endswith(".classify.json"):
        _fail(
            f"output must follow the `<image-stem>.classify.json` naming convention "
            f"(e.g. `<id>_p1.classify.json`), but `{name}` was written. Rewrite it with the "
            f".classify.json suffix next to the image."
        )

    if not p.exists():
        _fail(f"expected the classification file at {path}, but it does not exist on disk")

    try:
        obj = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as e:
        _fail(f"{name} is not valid JSON: {e}")

    if not isinstance(obj, dict):
        _fail(f"{name} must contain a single JSON object, got {type(obj).__name__}")

    _validate_fields(obj)
    _ok(f"classify output OK: {name}")


if __name__ == "__main__":
    main()
