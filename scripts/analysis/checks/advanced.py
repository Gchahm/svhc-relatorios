"""Layer 3: Advanced financial analysis."""

import logging
from collections import defaultdict

from common import det_id
from ..models import Alert, PeriodData, RefIndex
from .attachments import check_attachment_mismatches

logger = logging.getLogger(__name__)

CONCENTRATION_LIMIT = 0.30  # Alert if single supplier > 30% of total


def _alert(period: str, check_type: str, severity: str, title: str,
           description: str, metadata: dict, discriminator: str = "") -> Alert:
    return Alert(
        id=det_id("alert", period, check_type, discriminator),
        type=check_type,
        severity=severity,
        title=title,
        description=description,
        reference_period=period,
        metadata=metadata,
    )


def check_vendor_concentration(
    period: PeriodData, refs: RefIndex,
) -> list[Alert]:
    alerts = []
    total_expenses = period.report["total_expenses"]
    if total_expenses <= 0:
        return alerts

    vendor_totals: dict[str, float] = defaultdict(float)
    for e in period.debit_entries:
        if e.get("vendor_id"):
            vendor_totals[e["vendor_id"]] += e["amount"]

    for vendor_id, total in vendor_totals.items():
        pct = total / total_expenses
        if pct <= CONCENTRATION_LIMIT:
            continue
        name = refs.vendor_name(vendor_id)
        pct_fmt = round(pct * 100, 1)
        alerts.append(_alert(period.period, "vendor_concentration", "warning",
            f"{name}: {pct_fmt}% das despesas em {period.period}",
            f"'{name}' concentra R$ {total:.2f} de R$ {total_expenses:.2f} "
            f"em despesas ({pct_fmt}%), acima do limite de {CONCENTRATION_LIMIT * 100:.0f}%.",
            {"vendor_id": vendor_id, "vendor_name": name,
             "vendor_total": round(total, 2), "total_expenses": total_expenses,
             "pct": pct_fmt},
            discriminator=vendor_id,
        ))

    return alerts


def check_category_growth(
    period: PeriodData, all_periods: dict[str, PeriodData], refs: RefIndex,
) -> list[Alert]:
    alerts = []
    sorted_keys = sorted(k for k in all_periods if k < period.period)
    if len(sorted_keys) < 6:
        return alerts

    # Average of first 3 periods per subcategory
    first_3 = [all_periods[k] for k in sorted_keys[:3]]
    initial_avgs: dict[str, float] = defaultdict(float)
    initial_counts: dict[str, int] = defaultdict(int)
    for p in first_3:
        for sub in p.category_subtotals:
            if sub["movement_type"] == "D":
                initial_avgs[sub["subcategory_id"]] += sub["amount"]
                initial_counts[sub["subcategory_id"]] += 1
    for k in initial_avgs:
        initial_avgs[k] /= initial_counts[k]

    # Overall growth
    first_period = all_periods[sorted_keys[0]]
    initial_expenses = first_period.report["total_expenses"]
    if initial_expenses <= 0:
        return alerts
    overall_growth = (period.report["total_expenses"] - initial_expenses) / initial_expenses

    for sub in period.category_subtotals:
        if sub["movement_type"] != "D":
            continue
        avg = initial_avgs.get(sub["subcategory_id"])
        if not avg or avg <= 0:
            continue
        cat_growth = (sub["amount"] - avg) / avg
        if cat_growth > overall_growth * 2 and cat_growth > 1.0:
            sub_name = refs.subcategory_name(sub["subcategory_id"])
            cat_name = refs.category_name(sub["subcategory_id"])
            pct_cat = round(cat_growth * 100, 1)
            pct_overall = round(overall_growth * 100, 1)
            alerts.append(_alert(period.period, "category_growth_outlier", "warning",
                f"{sub_name} cresceu {pct_cat}% (geral: {pct_overall}%) em {period.period}",
                f"'{sub_name}' ({cat_name}): média inicial R$ {avg:.2f}, "
                f"atual R$ {sub['amount']:.2f} (crescimento {pct_cat}%). "
                f"Crescimento geral de despesas: {pct_overall}%.",
                {"subcategory": sub_name, "category": cat_name,
                 "initial_avg": round(avg, 2), "current": sub["amount"],
                 "growth_pct": pct_cat, "overall_growth_pct": pct_overall},
                discriminator=sub["subcategory_id"],
            ))

    return alerts


def check_seasonality(
    period: PeriodData, all_periods: dict[str, PeriodData],
) -> list[Alert]:
    alerts = []
    y, m = int(period.period[:4]), int(period.period[5:])
    same_month_last_year = f"{y - 1:04d}-{m:02d}"
    prev = all_periods.get(same_month_last_year)
    if not prev:
        return alerts

    for field, label in [("total_expenses", "despesas"), ("total_revenue", "receitas")]:
        current = period.report[field]
        previous = prev.report[field]
        if previous <= 0:
            continue
        pct = round((current - previous) / previous * 100, 1)
        if abs(pct) <= 50:
            continue
        direction = "aumento" if pct > 0 else "redução"
        severity = "warning" if abs(pct) > 100 else "info"
        alerts.append(_alert(period.period, f"seasonality_{label}", severity,
            f"{direction.capitalize()} de {abs(pct)}% em {label} vs mesmo mês do ano anterior",
            f"{label.capitalize()} em {period.period}: R$ {current:.2f}, "
            f"em {prev.period}: R$ {previous:.2f}. Variação interanual: {pct:+}%",
            {"field": field, "current": current, "previous_year": previous,
             "prev_period": prev.period, "pct": pct},
        ))

    return alerts


def check_delinquency(
    period: PeriodData, refs: RefIndex,
) -> list[Alert]:
    alerts = []
    total_units = len(refs.units)
    if total_units == 0:
        return alerts

    # Find subcategory for "TAXA DE CONDOMINIO"
    taxa_sub_ids = {
        sub_id for sub_id, sub in refs.subcategories.items()
        if "TAXA DE CONDOMINIO" in sub.get("name", "").upper()
    }
    if not taxa_sub_ids:
        return alerts

    paying_units = set()
    for e in period.entries:
        if e.get("unit_id") and e.get("subcategory_id") in taxa_sub_ids:
            paying_units.add(e["unit_id"])

    delinquent = total_units - len(paying_units)
    if delinquent <= 0:
        return alerts

    rate = delinquent / total_units
    pct = round(rate * 100, 1)
    severity = "critical" if rate > 0.15 else "warning" if rate > 0.05 else "info"

    alerts.append(_alert(period.period, "unit_delinquency", severity,
        f"Inadimplência: {delinquent} unidades ({pct}%) em {period.period}",
        f"{delinquent} de {total_units} unidades sem pagamento de taxa de "
        f"condomínio em {period.period} ({pct}%).",
        {"paying": len(paying_units), "total": total_units,
         "delinquent": delinquent, "rate_pct": pct},
    ))

    return alerts


# NOTE: the former ``check_duplicate_billing`` over-claim signal was retired in
# feature 020. Its entity-backed successor is ``check_document_overpayment``
# (``scripts/analysis/documents.py``), which reconciles the linked entries of a
# persisted ``documents`` row against its total across periods and emits the
# ``document_overpayment`` alert. Keeping both would double-report the same case.


SCORE_WEIGHTS = {"critical": 10, "warning": 5, "info": 1}


def run_advanced(
    period: PeriodData,
    all_periods: dict[str, PeriodData],
    refs: RefIndex,
) -> list[Alert]:
    alerts = []
    alerts.extend(check_vendor_concentration(period, refs))
    alerts.extend(check_category_growth(period, all_periods, refs))
    alerts.extend(check_seasonality(period, all_periods))
    alerts.extend(check_delinquency(period, refs))
    alerts.extend(check_attachment_mismatches(period, refs))

    logger.info("Advanced %s: %d alerts", period.period, len(alerts))
    return alerts
