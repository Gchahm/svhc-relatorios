"""CLI for the EXTRACT-002 vision transcriber: ``python -m doc_transcribe --image <path> ...``.

Thin wrapper over :func:`doc_transcribe.transcribe` — prints the typed-JSON result to stdout (exit 0).
A config/usage error (missing/unreadable image, missing optional dep/key, bad backend) prints a
readable message to stderr and exits non-zero. A bad *model response* is NOT an error: it prints the
result with ``parse_errors`` and still exits 0.
"""

from __future__ import annotations

import argparse
import json
import sys

from .backends import Backend, TranscribeError
from .transcribe import transcribe


def main(argv: list[str] | None = None, *, backend_impl: Backend | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m doc_transcribe",
        description="Transcribe a fiscal-document image into validated typed JSON.",
    )
    parser.add_argument("--image", required=True, help="path to the document page image")
    parser.add_argument("--type", default="auto", dest="doc_type", help="document type or 'auto' (default)")
    parser.add_argument("--backend", default="cli", choices=["cli", "api"], help="backend (default: cli)")
    parser.add_argument("--model", default=None, help="optional model override")
    args = parser.parse_args(argv)

    try:
        result = transcribe(
            args.image,
            args.doc_type,
            backend=args.backend,
            model=args.model,
            backend_impl=backend_impl,
        )
    except TranscribeError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
