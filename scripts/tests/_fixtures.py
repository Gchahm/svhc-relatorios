"""Shared in-memory fixtures for the analysis-core unit tests (TEST-002 / issue #69).

Pure Python — no D1/R2/network/playwright. Builds the same in-memory shapes the loader
assembles from D1 so the pure analysis functions can be exercised directly.
"""

from __future__ import annotations

from analysis.models import PeriodData, RefIndex


def make_report(
    *,
    total_revenue=0.0,
    total_expenses=0.0,
    month_balance=0.0,
    opening_balance=0.0,
    accumulated_balance=0.0,
) -> dict:
    return {
        "total_revenue": total_revenue,
        "total_expenses": total_expenses,
        "month_balance": month_balance,
        "opening_balance": opening_balance,
        "accumulated_balance": accumulated_balance,
    }


def make_period(
    period="2025-12",
    *,
    report=None,
    entries=None,
    category_subtotals=None,
    attachments=None,
    raw_extra=None,
) -> PeriodData:
    """Build a PeriodData with the same `raw` shape the loader produces."""
    entries = entries or []
    category_subtotals = category_subtotals or []
    attachments = attachments or []
    report = report if report is not None else make_report()
    raw = {
        "accountability_reports": [report],
        "entries": entries,
        "category_subtotals": category_subtotals,
        "attachments": attachments,
        "attachment_analyses": [],
        "alerts": [],
        "page_classifications": [],
    }
    if raw_extra:
        raw.update(raw_extra)
    return PeriodData(
        period=period,
        raw=raw,
        report=report,
        entries=entries,
        category_subtotals=category_subtotals,
        attachments=attachments,
    )


def make_refs(*, vendors=None, subcategories=None, categories=None, units=None, vendor_first_seen=None) -> RefIndex:
    refs = RefIndex()
    for v in vendors or []:
        refs.vendors[v["id"]] = v
    for s in subcategories or []:
        refs.subcategories[s["id"]] = s
    for c in categories or []:
        refs.categories[c["id"]] = c
    for u in units or []:
        refs.units[u["id"]] = u
    if vendor_first_seen:
        refs.vendor_first_seen = dict(vendor_first_seen)
    return refs


def entry(eid, *, amount, movement_type="D", vendor_id=None, unit_id=None, subcategory_id=None,
          date="2025-12-10", description="LANC"):
    e = {
        "id": eid,
        "amount": amount,
        "movement_type": movement_type,
        "date": date,
        "description": description,
    }
    if vendor_id is not None:
        e["vendor_id"] = vendor_id
    if unit_id is not None:
        e["unit_id"] = unit_id
    if subcategory_id is not None:
        e["subcategory_id"] = subcategory_id
    return e


def attachment(aid, entry_id, *, file_path="2025-12/x_p1.png", content_hash=None,
               classified_at=None, external_document_id=None):
    a = {"id": aid, "entry_id": entry_id, "file_path": file_path}
    a["content_hash"] = content_hash
    a["classified_at"] = classified_at
    a["external_document_id"] = external_document_id
    return a


def analysis_row(attachment_id, *, amount_match=None, vendor_match=None, date_match=None,
                 error=None, extracted_amount=None, issuer_name=None, extracted_date=None):
    return {
        "attachment_id": attachment_id,
        "amount_match": amount_match,
        "vendor_match": vendor_match,
        "date_match": date_match,
        "error": error,
        "extracted_amount": extracted_amount,
        "issuer_name": issuer_name,
        "extracted_date": extracted_date,
    }
