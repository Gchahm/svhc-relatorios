"""Layer 2: Trend analysis and anomaly detection."""

import logging
from collections import defaultdict

from common import det_id
from ..models import Alert, PeriodData, RefIndex

logger = logging.getLogger(__name__)

DEVIATION_THRESHOLD = 0.50  # Alert if > 50% above average


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


def check_subcategory_above_average(
    period: PeriodData, all_periods: dict[str, PeriodData], refs: RefIndex,
) -> list[Alert]:
    alerts = []
    prior = {k: v for k, v in all_periods.items() if k < period.period}
    if len(prior) < 2:
        return alerts

    # Historical averages per (subcategory_id, movement_type=D)
    hist: dict[str, list[float]] = defaultdict(list)
    for p in prior.values():
        for sub in p.category_subtotals:
            if sub["movement_type"] == "D":
                hist[sub["subcategory_id"]].append(sub["amount"])

    for sub in period.category_subtotals:
        if sub["movement_type"] != "D":
            continue
        values = hist.get(sub["subcategory_id"])
        if not values or len(values) < 2:
            continue
        avg = sum(values) / len(values)
        if avg <= 0:
            continue
        current = sub["amount"]
        limit = avg * (1 + DEVIATION_THRESHOLD)
        if current <= limit:
            continue
        pct_above = round((current - avg) / avg * 100, 1)
        sub_name = refs.subcategory_name(sub["subcategory_id"])
        cat_name = refs.category_name(sub["subcategory_id"])
        alerts.append(_alert(period.period, "subcategory_above_average", "warning",
            f"{sub_name} {pct_above}% acima da média em {period.period}",
            f"'{sub_name}' ({cat_name}): R$ {current:.2f} neste mês, "
            f"média histórica R$ {avg:.2f} ({len(values)} meses). "
            f"{pct_above}% acima da média.",
            {"subcategory": sub_name, "category": cat_name,
             "current": current, "average": round(avg, 2),
             "months": len(values), "pct_above": pct_above},
            discriminator=sub["subcategory_id"],
        ))

    return alerts


def check_month_over_month(
    period: PeriodData, all_periods: dict[str, PeriodData],
) -> list[Alert]:
    alerts = []
    sorted_keys = sorted(all_periods.keys())
    idx = sorted_keys.index(period.period)
    if idx == 0:
        return alerts
    prev = all_periods[sorted_keys[idx - 1]]

    for field, label in [("total_expenses", "despesas"), ("total_revenue", "receitas")]:
        current = period.report[field]
        previous = prev.report[field]
        if previous <= 0:
            continue
        pct = round((current - previous) / previous * 100, 1)
        if abs(pct) <= 30:
            continue
        direction = "aumento" if pct > 0 else "redução"
        alerts.append(_alert(period.period, f"month_variation_{label}", "info",
            f"{direction.capitalize()} de {abs(pct)}% em {label} em {period.period}",
            f"Total de {label} em {period.period}: R$ {current:.2f}, "
            f"mês anterior ({prev.period}): R$ {previous:.2f}. Variação: {pct:+}%",
            {"field": field, "current": current, "previous": previous,
             "prev_period": prev.period, "pct": pct},
        ))

    return alerts


def check_missing_recurring_subcategory(
    period: PeriodData, all_periods: dict[str, PeriodData], refs: RefIndex,
) -> list[Alert]:
    alerts = []
    sorted_keys = sorted(k for k in all_periods if k < period.period)
    if len(sorted_keys) < 3:
        return alerts

    # Subcategories in the last 3 periods
    last_3 = [all_periods[k] for k in sorted_keys[-3:]]
    sets = []
    for p in last_3:
        sets.append({sub["subcategory_id"] for sub in p.category_subtotals})

    recurring = sets[0] & sets[1] & sets[2]
    current = {sub["subcategory_id"] for sub in period.category_subtotals}
    missing = recurring - current

    for sub_id in missing:
        sub_name = refs.subcategory_name(sub_id)
        cat_name = refs.category_name(sub_id)
        alerts.append(_alert(period.period, "missing_recurring_subcategory", "info",
            f"'{sub_name}' ausente em {period.period}",
            f"Subcategoria '{sub_name}' ({cat_name}) estava presente nos últimos "
            f"3 meses mas não aparece em {period.period}.",
            {"subcategory": sub_name, "category": cat_name,
             "last_seen_in": [p.period for p in last_3]},
            discriminator=sub_id,
        ))

    return alerts


def run_trends(
    period: PeriodData,
    all_periods: dict[str, PeriodData],
    refs: RefIndex,
) -> list[Alert]:
    alerts = []
    alerts.extend(check_subcategory_above_average(period, all_periods, refs))
    alerts.extend(check_month_over_month(period, all_periods))
    alerts.extend(check_missing_recurring_subcategory(period, all_periods, refs))

    logger.info("Trends %s: %d alerts", period.period, len(alerts))
    return alerts
