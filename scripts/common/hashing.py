"""Content hashing shared by the scraper (capture-time write) and analysis (group/read).

The "same Nota Fiscal" grouping key is a content hash over an attachment's page-image
files. The source system attaches one NF to several entries as byte-identical copies, so
`file_path` (named per entry) and `external_document_id` (per entry) both differ across
siblings and the extracted NF number is noisy — the robust key is the page bytes.

This helper lives in ``common`` (alongside ``det_id``/``now_ms``) so BOTH subsystems can
import it without re-coupling: the scraper hashes the bytes it just downloaded and stores
``attachments.content_hash``; the analysis pipeline groups by that column (falling back to
this helper for rows captured before the column existed). Keeping one implementation makes
the stored value byte-identical to what grouping expects. Stdlib only.
"""

import hashlib
import pathlib

# Read files in chunks so a large multi-page PDF render doesn't load wholesale.
_CHUNK = 1 << 20


def split_paths(file_path: str | None) -> list[str]:
    """Page image paths from a attachment's ``;``-separated ``file_path``."""
    return [p.strip() for p in (file_path or "").split(";") if p.strip()]


def content_hash(file_path: str | None) -> str | None:
    """Joined md5 of an attachment's page image files.

    Paths are used as-is (resolved against the current working directory). Returns
    ``None`` if there are no pages or any page file cannot be read — callers MUST treat
    ``None`` as "ungroupable" and never merge such attachments. The per-page
    ``:{size}:`` length delimiter keeps ``[AB]`` and ``[A, B]`` from colliding; pages are
    hashed in order.
    """
    paths = split_paths(file_path)
    if not paths:
        return None

    digest = hashlib.md5()
    for path in paths:
        p = pathlib.Path(path)
        if not p.exists():
            return None
        try:
            with p.open("rb") as fh:
                while chunk := fh.read(_CHUNK):
                    digest.update(chunk)
        except OSError:
            return None
        # Length-delimit pages so [AB] and [A, B] can't collide.
        digest.update(f":{p.stat().st_size}:".encode())
    return digest.hexdigest()
