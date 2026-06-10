"""Per-attachment mismatch alerts (feature 018).

Turns the per-attachment amount/vendor/date mismatches and page-errors — previously only
visible through the ``mismatches`` CLI (the improve-loop's hand-back) — into user-facing,
drill-downable alerts. Detection is delegated to ``analysis.mismatches`` so this check and
``summarize_mismatches`` share a single source of truth (FR-004) and cannot drift.

One alert per (attachment, kind) with a distinct ``type`` per kind (so the alerts UI can
filter by it) and ``discriminator = attachment_id`` → a deterministic, stable id that makes
re-runs idempotent (FR-003), consistent with ``check_duplicate_billing``. Each alert's
metadata carries ``{attachment_id, entry_id, kind, ledger_value, extracted_value}`` so the
frontend can deep-link to the entry's validation dialog.
"""

import logging

from common import det_id

from ..mismatches import (
    KIND_AMOUNT,
    KIND_DATE,
    KIND_PAGE_ERROR,
    KIND_VENDOR,
    detect_attachment_mismatches,
)
from ..models import Alert, PeriodData, RefIndex

logger = logging.getLogger(__name__)

# (alert type, severity) per mismatch kind.
_TYPE_BY_KIND = {
    KIND_AMOUNT: ("attachment_amount_mismatch", "warning"),
    KIND_VENDOR: ("attachment_vendor_mismatch", "warning"),
    KIND_DATE: ("attachment_date_mismatch", "warning"),
    KIND_PAGE_ERROR: ("attachment_page_error", "info"),
}


def _money(value) -> str:
    return f"R$ {value:.2f}" if isinstance(value, (int, float)) else str(value)


def _title_description(period: str, kind: str, ledger, extracted, detail) -> tuple[str, str]:
    if kind == KIND_AMOUNT:
        return (
            f"Valor do comprovante diverge do lançamento em {period}",
            f"Valor extraído do comprovante ({_money(extracted)}) diverge do lançamento "
            f"({_money(ledger)}).",
        )
    if kind == KIND_VENDOR:
        return (
            f"Fornecedor do comprovante diverge do lançamento em {period}",
            f"Emitente do comprovante ('{extracted}') diverge do fornecedor do lançamento "
            f"('{ledger}').",
        )
    if kind == KIND_DATE:
        return (
            f"Data do comprovante fora do período {period}",
            f"Data extraída do comprovante ({extracted}) não corresponde ao período {period}.",
        )
    # page-error
    return (
        f"Comprovante ilegível em {period}",
        f"Não foi possível ler o comprovante: {detail}",
    )


def check_attachment_mismatches(period: PeriodData, refs: RefIndex) -> list[Alert]:
    """Emit one alert per (attachment, kind) for amount/vendor/date mismatches + page-errors."""
    alerts: list[Alert] = []
    for mm in detect_attachment_mismatches(period, refs):
        check_type, severity = _TYPE_BY_KIND[mm.kind]
        title, description = _title_description(
            period.period, mm.kind, mm.ledger_value, mm.extracted_value, mm.detail
        )
        metadata = {
            "attachment_id": mm.attachment_id,
            "entry_id": mm.entry_id,
            "kind": mm.kind,
            "ledger_value": mm.ledger_value,
            "extracted_value": mm.extracted_value,
        }
        if mm.detail is not None:
            metadata["detail"] = mm.detail
        alerts.append(
            Alert(
                id=det_id("alert", period.period, check_type, mm.attachment_id),
                type=check_type,
                severity=severity,
                title=title,
                description=description,
                reference_period=period.period,
                metadata=metadata,
            )
        )

    logger.info("Attachment mismatches %s: %d alerts", period.period, len(alerts))
    return alerts
