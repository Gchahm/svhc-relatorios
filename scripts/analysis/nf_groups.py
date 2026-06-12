"""Group attachments that share the same Nota Fiscal.

The source system attaches one NF to several accountability entries (line-item
splits, or principal vs. JUROS/MULTAS). Each entry stores its own copy of the
NF, but the copies are byte-identical. The robust "same NF" key is therefore a
content hash over the attachment's page image files — `file_path` (named per
entry) and `external_document_id` (per entry) both differ across siblings, and
the extracted NF number is noisy, so neither is usable as the primary key.

The hash is computed once at scrape time and persisted as ``attachments.content_hash``
(see ``common.hashing.content_hash``, re-exported here for existing callers). Grouping
therefore reads that column; for rows captured before the column existed it falls back to
computing the hash from the (materialized) page files, so behavior is identical on legacy
data.

Used by both the attachment-analysis stage (dedup + group reconciliation) and the
duplicate-billing check, so the definition of "same NF" lives in one place.
"""

from common.hashing import content_hash  # re-exported: the canonical "same NF" key

# Reconciliation tolerance, reused from the existing conventions: attachments.py
# uses a 5% relative band for amount-match and consistency.py uses R$ 0.05 for
# rounding. A group reconciles if it falls within EITHER, which keeps small
# totals (rounding-dominated) and large totals (percentage-dominated) both sane.
#
# DRIFT GUARD (IMP-006 / issue #43): this over/within/under decision is mirrored in
# TypeScript by ``documentStatus`` in ``src/lib/documents.ts`` (REL_TOL/ABS_TOL), which
# drives the /dashboard/documents badge. The two MUST stay in lockstep — a divergence makes
# the UI badge and the ``document_overpayment`` alert disagree. They are bound by the shared
# fixture ``scripts/analysis/reconciliation_contract.json`` and cross-language contract tests
# (``scripts/tests/test_reconciliation_contract.py`` + ``src/lib/documents.test.mjs``):
# change a constant or comparison here and you MUST update documents.ts AND the fixture, or a
# contract test fails.
AMOUNT_REL_TOL = 0.05
AMOUNT_ABS_TOL = 0.05

__all__ = ["content_hash", "within_tolerance", "reconcile_group", "group_attachments"]


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


def _group_key(doc: dict) -> str:
    """The "same NF" key for one attachment.

    Prefers the persisted ``content_hash`` column (written at scrape time). For a row
    captured before that column existed it falls back to hashing the attachment's
    (materialized) page files — identical to the historical behavior. An attachment whose
    pages can't be hashed gets a singleton key derived from its id, so a read failure or a
    missing hash never merges distinct attachments.
    """
    key = doc.get("content_hash")
    if key:
        return key
    key = content_hash(doc.get("file_path"))
    if key:
        return key
    return f"doc:{doc['id']}"


def group_attachments(attachments: list[dict]) -> dict[str, list[dict]]:
    """Map a "same NF" key to the attachments whose page bytes are identical.

    Attachments that share the same content hash (``content_hash`` column, else a
    fallback hash of their page files) land under one key. A attachment with no usable
    hash gets its own singleton group keyed by its id, so a missing/unreadable hash never
    merges distinct attachments. The common single-entry case yields singleton groups,
    letting callers preserve their existing per-attachment behavior.
    """
    groups: dict[str, list[dict]] = {}
    for doc in attachments:
        groups.setdefault(_group_key(doc), []).append(doc)
    return groups
