"""Shared per-attachment mismatch detection (single source of truth).

Both the user-facing alert check (``checks.attachments.check_attachment_mismatches``) and
the self-improving loop's terse ``extractions.summarize_mismatches`` derive per-attachment
mismatches from the SAME function here, so the alerts page and the ``mismatches`` CLI can
never drift (feature 018, FR-004).

A mismatch is read from the PERSISTED ``attachment_analyses`` match flags
(``amount_match`` / ``vendor_match`` / ``date_match`` / ``error``), which already encode the
shared-NF group reconciliation applied by ``apply_extractions`` — so a split that reconciles
within tolerance carries ``amount_match = 1`` and yields no amount mismatch here (FR-012).
This module is therefore a thin, deterministic read; it imports no pipeline machinery (only
the model/ref types it is handed), keeping it free of the ``checks`` ⇄ ``extractions`` import
cycle.
"""

from __future__ import annotations

from dataclasses import dataclass

from .models import PeriodData, RefIndex

KIND_AMOUNT = "amount"
KIND_VENDOR = "vendor"
KIND_DATE = "date"
KIND_PAGE_ERROR = "page-error"


@dataclass
class AttachmentMismatch:
    """One disagreement between an attachment's extraction and the ledger.

    A single attachment may produce multiple mismatches (amount + vendor + date), but at
    most one per ``kind``. ``ledger_value`` / ``extracted_value`` are the two sides being
    compared; ``detail`` carries the error string for a ``page-error``.
    """

    period: str
    attachment_id: str
    entry_id: str | None
    kind: str
    ledger_value: float | str | None = None
    extracted_value: float | str | None = None
    detail: str | None = None


def detect_attachment_mismatches(period: PeriodData, refs: RefIndex) -> list[AttachmentMismatch]:
    """Per-attachment mismatches for one period, read from persisted ``attachment_analyses``.

    For each analysis, resolve its entry via ``attachments[attachment_id].entry_id``. A
    ``page-error`` short-circuits the field checks for that attachment; otherwise each of
    ``amount`` / ``vendor`` / ``date`` whose persisted match flag is ``0`` becomes a
    mismatch. Reconciliation is already baked into those flags (no recompute).
    """
    entry_map = {e["id"]: e for e in period.entries}
    doc_map = {d["id"]: d for d in period.attachments}

    out: list[AttachmentMismatch] = []
    for a in period.raw.get("attachment_analyses", []):
        doc = doc_map.get(a["attachment_id"])
        entry_id = doc.get("entry_id") if doc else None
        entry = entry_map.get(entry_id) if entry_id else None

        if a.get("error"):
            out.append(
                AttachmentMismatch(
                    period.period, a["attachment_id"], entry_id, KIND_PAGE_ERROR, detail=a["error"]
                )
            )
            continue

        if a.get("amount_match") == 0:
            out.append(
                AttachmentMismatch(
                    period.period,
                    a["attachment_id"],
                    entry_id,
                    KIND_AMOUNT,
                    ledger_value=entry.get("amount") if entry else None,
                    extracted_value=a.get("extracted_amount"),
                )
            )
        if a.get("vendor_match") == 0:
            vendor = refs.vendor_name(entry["vendor_id"]) if entry and entry.get("vendor_id") else None
            out.append(
                AttachmentMismatch(
                    period.period,
                    a["attachment_id"],
                    entry_id,
                    KIND_VENDOR,
                    ledger_value=vendor,
                    extracted_value=a.get("issuer_name"),
                )
            )
        if a.get("date_match") == 0:
            out.append(
                AttachmentMismatch(
                    period.period,
                    a["attachment_id"],
                    entry_id,
                    KIND_DATE,
                    ledger_value=period.period,
                    extracted_value=a.get("extracted_date"),
                )
            )
    return out
