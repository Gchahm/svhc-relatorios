"""Load period data from Cloudflare D1 and build analysis data structures.

Reads each period's rows straight from D1 (via ``common.d1``) and assembles the same
per-period ``raw`` dict the pipeline used to read from ``data/scrape/<period>.json`` —
same keys, with ``attachment_analysis_records`` re-nested under their parent as
``analysis_records`` and the records' ``response`` JSON decoded back to objects. Every
downstream consumer (checks, select_work, summarize_mismatches, nf_groups, loop_state)
reads this in-memory shape, so swapping the source from files to D1 leaves them unchanged.
"""

import json
import logging
from collections import defaultdict

from common import d1
from common.d1 import Target

from .models import PeriodData, RefIndex

logger = logging.getLogger(__name__)


def _sql_str(value: str) -> str:
    return "'" + str(value).replace("'", "''") + "'"


def _in_clause(ids) -> str | None:
    """SQL ``(...)`` list for an IN clause, or None when there are no ids."""
    vals = ",".join(_sql_str(i) for i in ids)
    return f"({vals})" if vals else None


def _all_periods(target: Target) -> list[str]:
    rows = d1.query("SELECT period FROM accountability_reports", target=target)
    return sorted(r["period"] for r in rows)


def _load_period_raw(period: str, target: Target) -> dict | None:
    """Assemble the per-period ``raw`` dict from D1 (same shape as the old period JSON)."""
    reports = d1.query(
        f"SELECT * FROM accountability_reports WHERE period = {_sql_str(period)}", target=target
    )
    if not reports:
        return None
    report = reports[0]
    rid = report["id"]

    entries = d1.query(f"SELECT * FROM entries WHERE report_id = {_sql_str(rid)}", target=target)
    subtotals = d1.query(f"SELECT * FROM category_subtotals WHERE report_id = {_sql_str(rid)}", target=target)
    approvers = d1.query(f"SELECT * FROM approvers WHERE report_id = {_sql_str(rid)}", target=target)
    # `classified_at` lives in the analysis-owned `attachment_state` table, NOT on the
    # `attachments` mirror (BUG-002 / issue #33). LEFT JOIN it so each attachment dict still
    # carries `classified_at` (NULL = pending) for select_work / loop-state / mismatches.
    attachments = d1.query(
        "SELECT d.*, s.classified_at AS classified_at "
        "FROM attachments d JOIN entries e ON d.entry_id = e.id "
        "LEFT JOIN attachment_state s ON s.attachment_id = d.id "
        f"WHERE e.report_id = {_sql_str(rid)}",
        target=target,
    )
    runs = (
        d1.query(f"SELECT * FROM scrape_runs WHERE id = {_sql_str(report['scrape_run_id'])}", target=target)
        if report.get("scrape_run_id")
        else []
    )

    # Per-period reference membership, derived from the entries/subtotals that use them
    # (so vendor/category/unit/subcategory lists mirror the old per-period JSON exactly).
    vendor_ids = {e["vendor_id"] for e in entries if e.get("vendor_id")}
    subcat_ids = {e["subcategory_id"] for e in entries if e.get("subcategory_id")}
    subcat_ids |= {s["subcategory_id"] for s in subtotals if s.get("subcategory_id")}
    unit_ids = {e["unit_id"] for e in entries if e.get("unit_id")}

    vendors = (
        d1.query(f"SELECT * FROM vendors WHERE id IN {_in_clause(vendor_ids)}", target=target) if vendor_ids else []
    )
    subcategories = (
        d1.query(f"SELECT * FROM subcategories WHERE id IN {_in_clause(subcat_ids)}", target=target)
        if subcat_ids
        else []
    )
    cat_ids = {s["category_id"] for s in subcategories if s.get("category_id")}
    categories = (
        d1.query(f"SELECT * FROM categories WHERE id IN {_in_clause(cat_ids)}", target=target) if cat_ids else []
    )
    units = d1.query(f"SELECT * FROM units WHERE id IN {_in_clause(unit_ids)}", target=target) if unit_ids else []

    # Attachment analyses for this period (join through attachments->entries), with the
    # normalized per-page records re-nested as analysis_records and their response decoded.
    analyses = d1.query(
        "SELECT da.* FROM attachment_analyses da "
        "JOIN attachments d ON da.attachment_id = d.id "
        f"JOIN entries e ON d.entry_id = e.id WHERE e.report_id = {_sql_str(rid)}",
        target=target,
    )
    if analyses:
        an_ids = [a["id"] for a in analyses]
        records = d1.query(
            f"SELECT * FROM attachment_analysis_records WHERE attachment_analysis_id IN {_in_clause(an_ids)}",
            target=target,
        )
        for r in records:
            resp = r.get("response")
            if isinstance(resp, str):
                try:
                    r["response"] = json.loads(resp) if resp else None
                except json.JSONDecodeError:
                    r["response"] = None
        by_analysis: dict[str, list[dict]] = defaultdict(list)
        for r in records:
            by_analysis[r["attachment_analysis_id"]].append(r)
        for a in analyses:
            a["analysis_records"] = by_analysis.get(a["id"], [])

    # Per-page classification staging rows (the merge's per-page extraction input), joined
    # through attachments->entries to the report. Decode each row's `response` JSON back to an
    # object so D1ExtractionProvider serves parsed fields (mirrors the analysis_records decode).
    page_classifications = d1.query(
        "SELECT pc.* FROM page_classifications pc "
        "JOIN attachments d ON pc.attachment_id = d.id "
        f"JOIN entries e ON d.entry_id = e.id WHERE e.report_id = {_sql_str(rid)}",
        target=target,
    )
    for pc in page_classifications:
        resp = pc.get("response")
        if isinstance(resp, str):
            try:
                pc["response"] = json.loads(resp) if resp else None
            except json.JSONDecodeError:
                pc["response"] = None

    alerts = d1.query(f"SELECT * FROM alerts WHERE reference_period = {_sql_str(period)}", target=target)

    return {
        "scrape_runs": runs,
        "categories": categories,
        "vendors": vendors,
        "units": units,
        "subcategories": subcategories,
        "accountability_reports": [report],
        "entries": entries,
        "category_subtotals": subtotals,
        "approvers": approvers,
        "attachments": attachments,
        "page_classifications": page_classifications,
        "attachment_analyses": analyses,
        "alerts": alerts,
    }


def load_all_periods(
    target: Target = "local",
    periods_filter: list[str] | None = None,
) -> tuple[dict[str, PeriodData], RefIndex]:
    """Load periods from D1 and build the merged reference index.

    Returns (periods dict sorted chronologically, merged RefIndex).
    """
    target_periods = periods_filter if periods_filter else _all_periods(target)

    refs = RefIndex()
    periods: dict[str, PeriodData] = {}

    for period in sorted(set(target_periods)):
        raw = _load_period_raw(period, target)
        if raw is None or not raw.get("accountability_reports"):
            logger.warning("Skipping %s: no accountability report", period)
            continue

        refs.merge_period(raw, period)
        periods[period] = PeriodData(
            period=period,
            raw=raw,
            report=raw["accountability_reports"][0],
            entries=raw.get("entries", []),
            category_subtotals=raw.get("category_subtotals", []),
            attachments=raw.get("attachments", []),
        )

    # vendor_first_seen needs full cross-period context (a vendor's earliest period),
    # independent of the filter — one global query gives the authoritative answer.
    fs_rows = d1.query(
        "SELECT e.vendor_id AS vendor_id, MIN(r.period) AS first_period "
        "FROM entries e JOIN accountability_reports r ON e.report_id = r.id "
        "WHERE e.vendor_id IS NOT NULL GROUP BY e.vendor_id",
        target=target,
    )
    refs.vendor_first_seen = {row["vendor_id"]: row["first_period"] for row in fs_rows}

    logger.info("Loaded %d period(s) with %d subcategories, %d vendors, %d units",
                len(periods), len(refs.subcategories), len(refs.vendors), len(refs.units))

    return dict(sorted(periods.items())), refs
