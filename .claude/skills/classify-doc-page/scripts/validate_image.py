#!/usr/bin/env python3
"""PreToolUse validator for the `classify-doc-page` skill.

Runs before every Read in the skill. It makes sure the file the agent is about to
read is a real image: the path must exist, be a regular non-empty file, and carry
a recognized image signature (magic bytes — the extension is not trusted). The
skill's own JSON template read is allowed through.

On a violation it exits 2 with a message on stderr — for a PreToolUse hook this
blocks the Read and feeds the message back to the model, so it can report the bad
input (e.g. write `{"error": "..."}`) instead of trying to classify a non-image.
On success (or for the template read) it exits 0.

Input: the PreToolUse hook JSON on stdin (uses `tool_input.file_path`). For manual
testing, a file path may be passed as the first CLI argument instead. Stdlib only.
"""

import json
import sys
from pathlib import Path

# First-bytes signatures for the image formats a rendered fiscal page may be.
_MAX_SNIFF = 32


def _fail(msg: str) -> None:
    """Block the Read and report why back to the model."""
    sys.stderr.write(f"[classify-doc-page] input is not a valid image: {msg}\n")
    sys.exit(2)


def _written_path() -> str | None:
    """The path the Read tool is about to open, from CLI arg or hook stdin JSON."""
    if len(sys.argv) > 1 and sys.argv[1].strip():
        return sys.argv[1].strip()
    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        return None
    tool_input = payload.get("tool_input") or {}
    path = tool_input.get("file_path") or tool_input.get("path")
    return path.strip() if isinstance(path, str) and path.strip() else None


def _sniff_image(data: bytes) -> str | None:
    """Return the image format name from magic bytes, or None if unrecognized."""
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "png"
    if data.startswith(b"\xff\xd8\xff"):
        return "jpeg"
    if data[:6] in (b"GIF87a", b"GIF89a"):
        return "gif"
    if data.startswith(b"BM"):
        return "bmp"
    if data[:4] in (b"II*\x00", b"MM\x00*"):
        return "tiff"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "webp"
    return None


def main() -> None:
    path = _written_path()
    if path is None:
        # Can't determine the target — don't block on hook plumbing issues.
        sys.exit(0)

    p = Path(path)

    # The skill legitimately reads its JSON template; that read is not an image.
    if p.suffix.lower() == ".json":
        sys.exit(0)

    if not p.exists():
        _fail(f"`{path}` is not a valid file path (does not exist)")
    if not p.is_file():
        _fail(f"`{path}` is not a regular file")

    try:
        with p.open("rb") as fh:
            head = fh.read(_MAX_SNIFF)
    except OSError as e:
        _fail(f"`{path}` could not be read: {e}")

    if not head:
        _fail(f"`{path}` is empty")

    fmt = _sniff_image(head)
    if fmt is None:
        _fail(
            f"`{p.name}` does not look like an image (no PNG/JPEG/GIF/BMP/TIFF/WEBP signature). "
            f"This skill classifies page IMAGES only."
        )

    print(f"[classify-doc-page] input image OK ({fmt}): {p.name}")
    sys.exit(0)


if __name__ == "__main__":
    main()
