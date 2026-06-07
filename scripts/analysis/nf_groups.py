"""Group documents that share the same Nota Fiscal.

The source system attaches one NF to several accountability entries (line-item
splits, or principal vs. JUROS/MULTAS). Each entry stores its own copy of the
NF, but the copies are byte-identical. The robust "same NF" key is therefore a
content hash over the document's page image files — `file_path` (named per
entry) and `external_document_id` (per entry) both differ across siblings, and
the extracted NF number is noisy, so neither is usable as the primary key.

Used by both the document-analysis stage (dedup + group reconciliation) and the
duplicate-billing check, so the definition of "same NF" lives in one place.
"""

import hashlib
import pathlib

# Read files in chunks so a large multi-page PDF render doesn't load wholesale.
_CHUNK = 1 << 20

# Reconciliation tolerance, reused from the existing conventions: documentos.py
# uses a 5% relative band for amount-match and consistency.py uses R$ 0.05 for
# rounding. A group reconciles if it falls within EITHER, which keeps small
# totals (rounding-dominated) and large totals (percentage-dominated) both sane.
AMOUNT_REL_TOL = 0.05
AMOUNT_ABS_TOL = 0.05


def within_tolerance(value: float, reference: float) -> bool:
    """True when ``value`` matches ``reference`` within the rounding/relative band."""
    diff = abs(value - reference)
    if diff <= AMOUNT_ABS_TOL:
        return True
    return reference > 0 and diff / reference < AMOUNT_REL_TOL


def reconcile_group(sibling_sum: float, nf_total: float | None) -> str | None:
    """Classify a shared-NF group by comparing the sibling sum to the NF total.

    Returns one of:
      - "reconciled"  — sum matches the NF total within tolerance (legitimate split)
      - "over_claim"  — sum exceeds the NF total (duplicate-billing / over-claim)
      - "under_claim" — sum is below the NF total (incomplete split)
      - None          — NF total is missing/non-positive, so it can't be reconciled
    """
    if nf_total is None or nf_total <= 0:
        return None
    if within_tolerance(sibling_sum, nf_total):
        return "reconciled"
    return "over_claim" if sibling_sum > nf_total else "under_claim"


def _split_paths(file_path: str) -> list[str]:
    """Page image paths from a document's ``;``-separated ``file_path``."""
    return [p.strip() for p in (file_path or "").split(";") if p.strip()]


def content_hash(file_path: str) -> str | None:
    """Joined md5 of a document's page image files.

    Paths are used as-is (resolved against the current working directory, the
    same way ``documentos.py`` reads them). Returns ``None`` if there are no
    pages or any page file cannot be read — callers must treat ``None`` as
    "ungroupable" and never merge such documents.
    """
    paths = _split_paths(file_path)
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


def group_documents(documents: list[dict]) -> dict[str, list[dict]]:
    """Map a "same NF" key to the documents whose page bytes are identical.

    Documents that share byte-identical pages land under one content-hash key.
    A document whose pages can't be hashed (missing/unreadable) gets its own
    singleton group keyed by its id, so a read failure never merges distinct
    documents. The common single-entry case yields singleton groups, letting
    callers preserve their existing per-document behavior.
    """
    groups: dict[str, list[dict]] = {}
    for doc in documents:
        key = content_hash(doc.get("file_path"))
        if key is None:
            key = f"doc:{doc['id']}"
        groups.setdefault(key, []).append(doc)
    return groups
