"""Pluggable model-call backends for the EXTRACT-002 vision transcriber.

Two backends behind one tiny ``Backend`` protocol, so the rest of the module is independent of which
one ran (FR-004):

- ``CliBackend`` (default) — shells out to the ``claude`` binary (``claude -p``, headless Claude Code)
  in its own subprocess. Needs NO ``anthropic`` SDK and NO ``ANTHROPIC_API_KEY``; keeps page images out
  of any orchestrator's context.
- ``ApiBackend`` — calls the Anthropic Messages API via the **optional** ``anthropic`` SDK, sending the
  type's JSON Schema as a structured-output ``output_config.format`` so the typed shape is enforced at
  the wire. Needs ``ANTHROPIC_API_KEY``. The SDK is imported lazily INSIDE the method so this module
  imports with ``anthropic`` absent (FR-007).

Schema validation lives ABOVE the backend (in ``transcribe.py``) — a backend only returns the raw JSON
text the model produced. The ``cli`` backend has no wire enforcement, which is exactly why the module's
own parse + validate layer is mandatory. Zero imports from ``scripts/analysis``; no top-level
``anthropic`` import.
"""

from __future__ import annotations

import importlib
import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Protocol

# Default model for the api backend (best fidelity for dense fiscal documents; design T4). The cli
# backend uses whatever model the local Claude Code session is configured with unless a model is given.
DEFAULT_API_MODEL = "claude-opus-4-8"

# Subprocess wall-clock cap for the cli backend (a single page transcription).
_CLI_TIMEOUT_SECONDS = 300

_MAGIC_MEDIA_TYPES = (
    (b"\x89PNG\r\n\x1a\n", "image/png"),
    (b"\xff\xd8\xff", "image/jpeg"),
    (b"GIF87a", "image/gif"),
    (b"GIF89a", "image/gif"),
)

_EXT_MEDIA_TYPES = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".gif": "image/gif",
    ".webp": "image/webp",
}

_MEDIA_TYPE_SUFFIX = {
    "image/png": ".png",
    "image/jpeg": ".jpg",
    "image/gif": ".gif",
    "image/webp": ".webp",
}


class TranscribeError(RuntimeError):
    """A configuration/usage error (bad backend, missing optional dep/key, unreadable image).

    Raised at CALL time, never at import — a bad *model response* is NOT a TranscribeError (it is
    surfaced as ``parse_errors`` on the returned result).
    """


class Backend(Protocol):
    """The swappable model-call seam. Returns the raw JSON text the model produced."""

    def transcribe_to_json(self, *, image_bytes: bytes, media_type: str, schema: dict, instruction: str) -> str: ...


def media_type_for(source: str | os.PathLike | bytes) -> str:
    """Best-effort image media type from a path extension or raw bytes' magic number.

    Defaults to ``image/png`` when undetermined (PNG is the page-image format in this repo)."""
    if isinstance(source, (str, os.PathLike)):
        ext = Path(source).suffix.lower()
        if ext in _EXT_MEDIA_TYPES:
            return _EXT_MEDIA_TYPES[ext]
        return "image/png"
    for magic, mt in _MAGIC_MEDIA_TYPES:
        if source.startswith(magic):
            return mt
    if source[:4] == b"RIFF" and source[8:12] == b"WEBP":
        return "image/webp"
    return "image/png"


def extract_json(text: str) -> dict | None:
    """Best-effort recovery of a JSON object from a model's text answer (never raises).

    (1) Strip a leading/trailing markdown code fence (``` ```json ``` ... ``` ``` ```), then
    ``json.loads`` the whole thing. (2) On failure, scan for the largest balanced top-level
    ``{...}`` substring and parse that. Returns the parsed object, or ``None`` if nothing parses
    or the parsed value is not a dict.
    """
    if not isinstance(text, str):
        return None
    stripped = _strip_code_fence(text.strip())
    obj = _try_load_object(stripped)
    if obj is not None:
        return obj
    span = _largest_balanced_object(stripped)
    if span is not None:
        return _try_load_object(span)
    return None


def _try_load_object(text: str) -> dict | None:
    try:
        value = json.loads(text)
    except (ValueError, TypeError):
        return None
    return value if isinstance(value, dict) else None


def _strip_code_fence(text: str) -> str:
    if not text.startswith("```"):
        return text
    # Drop the opening fence line (``` or ```json) and a trailing fence if present.
    newline = text.find("\n")
    if newline == -1:
        return text
    body = text[newline + 1 :]
    fence_end = body.rfind("```")
    if fence_end != -1:
        body = body[:fence_end]
    return body.strip()


def _largest_balanced_object(text: str) -> str | None:
    """Return the first top-level balanced ``{...}`` substring (string-literal aware), or None."""
    start = text.find("{")
    if start == -1:
        return None
    depth = 0
    in_string = False
    escaped = False
    for i in range(start, len(text)):
        ch = text[i]
        if in_string:
            if escaped:
                escaped = False
            elif ch == "\\":
                escaped = True
            elif ch == '"':
                in_string = False
            continue
        if ch == '"':
            in_string = True
        elif ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return text[start : i + 1]
    return None


def _bytes_to_temp_image(image_bytes: bytes, media_type: str) -> str:
    suffix = _MEDIA_TYPE_SUFFIX.get(media_type, ".png")
    fd, path = tempfile.mkstemp(prefix="doc_transcribe_", suffix=suffix)
    with os.fdopen(fd, "wb") as fh:
        fh.write(image_bytes)
    return path


class CliBackend:
    """Shell out to ``claude -p`` (headless Claude Code). No SDK, no API key."""

    def __init__(self, model: str | None = None) -> None:
        self.model = model

    def transcribe_to_json(self, *, image_bytes: bytes, media_type: str, schema: dict, instruction: str) -> str:
        binary = shutil.which("claude")
        if binary is None:
            raise TranscribeError("the 'cli' backend requires the 'claude' binary on PATH (Claude Code).")
        image_path = _bytes_to_temp_image(image_bytes, media_type)
        cleanup = True
        try:
            image_dir = str(Path(image_path).parent)
            prompt = f"Read the image file at {image_path}\n\n{instruction}"
            # The prompt is fed via stdin (not as a positional arg): claude's --add-dir is variadic,
            # so a positional prompt after it is swallowed as another directory. stdin is unambiguous.
            argv = ["claude", "-p", "--output-format", "text", "--add-dir", image_dir]
            if self.model:
                argv += ["--model", self.model]
            try:
                proc = subprocess.run(
                    argv,
                    input=prompt,
                    capture_output=True,
                    text=True,
                    timeout=_CLI_TIMEOUT_SECONDS,
                )
            except (OSError, subprocess.SubprocessError) as exc:
                raise TranscribeError(f"the 'cli' backend failed to run 'claude': {exc}") from exc
            if proc.returncode != 0:
                raise TranscribeError(
                    f"the 'cli' backend's 'claude' call exited {proc.returncode}: {proc.stderr.strip()[:500]}"
                )
            return proc.stdout
        finally:
            if cleanup:
                try:
                    os.unlink(image_path)
                except OSError:
                    pass


class ApiBackend:
    """Call the Anthropic Messages API via the optional ``anthropic`` SDK with a wire-enforced schema."""

    def __init__(self, model: str = DEFAULT_API_MODEL) -> None:
        self.model = model

    def build_request(self, *, image_bytes: bytes, media_type: str, schema: dict, instruction: str) -> dict:
        """Pure builder for the ``messages.create`` kwargs (no SDK needed to construct it)."""
        import base64

        data = base64.standard_b64encode(image_bytes).decode("ascii")
        return {
            "model": self.model,
            "max_tokens": 8000,
            "thinking": {"type": "adaptive"},
            "output_config": {"format": {"type": "json_schema", "schema": schema}},
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "image", "source": {"type": "base64", "media_type": media_type, "data": data}},
                        {"type": "text", "text": instruction},
                    ],
                }
            ],
        }

    def transcribe_to_json(self, *, image_bytes: bytes, media_type: str, schema: dict, instruction: str) -> str:
        try:
            anthropic = importlib.import_module("anthropic")
        except ImportError as exc:
            raise TranscribeError(
                "the 'api' backend requires the anthropic SDK; install the api extra (pip install anthropic)."
            ) from exc
        if not os.environ.get("ANTHROPIC_API_KEY"):
            raise TranscribeError("the 'api' backend requires ANTHROPIC_API_KEY to be set.")
        client = anthropic.Anthropic()
        request = self.build_request(
            image_bytes=image_bytes, media_type=media_type, schema=schema, instruction=instruction
        )
        message = client.messages.create(**request)
        return _text_from_message(message)


def _text_from_message(message: object) -> str:
    """Concatenate the text blocks of an Anthropic Message response into one string."""
    content = getattr(message, "content", None)
    if content is None and isinstance(message, dict):
        content = message.get("content")
    parts: list[str] = []
    for block in content or []:
        block_type = getattr(block, "type", None) if not isinstance(block, dict) else block.get("type")
        if block_type == "text":
            text = getattr(block, "text", None) if not isinstance(block, dict) else block.get("text")
            if isinstance(text, str):
                parts.append(text)
    return "".join(parts)
