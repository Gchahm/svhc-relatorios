"""Layer 1: Consistency checks on a single period's data."""

import logging
from collections import defaultdict

from ...utils import det_id
from ..models import Alert, PeriodData, RefIndex

logger = logging.getLogger(__name__)

TOLERANCE = 0.05  # R$ 0.05 for rounding


def _approx_eq(a: float, b: float) -> bool:
    return abs(a - b) <= TOLERANCE


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


def check_balance_month(p: PeriodData) -> list[Alert]:
    r = p.report
    expected = r["total_revenue"] - r["total_expenses"]
    actual = r["month_balance"]
    if _approx_eq(actual, expected):
        return []
    return [_alert(p.period, "balance_month_mismatch", "critical",
        f"Saldo do mês inconsistente em {p.period}",
        f"Saldo reportado: R$ {actual:.2f}, "
        f"mas receitas ({r['total_revenue']:.2f}) - despesas ({r['total_expenses']:.2f}) "
        f"= R$ {expected:.2f}. Diferença: R$ {actual - expected:.2f}",
        {"reported": actual, "expected": expected, "difference": round(actual - expected, 2)},
    )]


def check_balance_accumulated(p: PeriodData) -> list[Alert]:
    r = p.report
    expected = r["opening_balance"] + r["month_balance"]
    actual = r["accumulated_balance"]
    if _approx_eq(actual, expected):
        return []
    return [_alert(p.period, "balance_accumulated_mismatch", "critical",
        f"Saldo acumulado inconsistente em {p.period}",
        f"Saldo acumulado reportado: R$ {actual:.2f}, "
        f"mas saldo inicial ({r['opening_balance']:.2f}) + saldo mês ({r['month_balance']:.2f}) "
        f"= R$ {expected:.2f}. Diferença: R$ {actual - expected:.2f}",
        {"reported": actual, "expected": expected, "difference": round(actual - expected, 2)},
    )]


def check_balance_continuity(p: PeriodData, all_periods: dict[str, PeriodData]) -> list[Alert]:
    sorted_keys = sorted(all_periods.keys())
    idx = sorted_keys.index(p.period)
    if idx == 0:
        return []
    prev = all_periods[sorted_keys[idx - 1]]
    prev_accumulated = prev.report["accumulated_balance"]
    current_opening = p.report["opening_balance"]
    if _approx_eq(current_opening, prev_accumulated):
        return []
    return [_alert(p.period, "balance_opening_mismatch", "critical",
        f"Saldo inicial de {p.period} não bate com saldo acumulado de {prev.period}",
        f"Saldo inicial: R$ {current_opening:.2f}, "
        f"saldo acumulado de {prev.period}: R$ {prev_accumulated:.2f}. "
        f"Diferença: R$ {current_opening - prev_accumulated:.2f}",
        {"opening": current_opening, "prev_accumulated": prev_accumulated,
         "prev_period": prev.period, "difference": round(current_opening - prev_accumulated, 2)},
    )]


def check_entries_vs_totals(p: PeriodData) -> list[Alert]:
    alerts = []
    r = p.report

    if not _approx_eq(p.total_debits, r["total_expenses"]):
        diff = p.total_debits - r["total_expenses"]
        alerts.append(_alert(p.period, "entries_expenses_mismatch", "warning",
            f"Soma de débitos diverge do total de despesas em {p.period}",
            f"Soma dos lançamentos D: R$ {p.total_debits:.2f}, "
            f"total despesas reportado: R$ {r['total_expenses']:.2f}. "
            f"Diferença: R$ {diff:.2f}",
            {"sum_entries": p.total_debits, "reported": r["total_expenses"], "difference": round(diff, 2)},
        ))

    if not _approx_eq(p.total_credits, r["total_revenue"]):
        diff = p.total_credits - r["total_revenue"]
        alerts.append(_alert(p.period, "entries_revenue_mismatch", "warning",
            f"Soma de créditos diverge do total de receitas em {p.period}",
            f"Soma dos lançamentos C: R$ {p.total_credits:.2f}, "
            f"total receitas reportado: R$ {r['total_revenue']:.2f}. "
            f"Diferença: R$ {diff:.2f}",
            {"sum_entries": p.total_credits, "reported": r["total_revenue"], "difference": round(diff, 2)},
        ))

    return alerts


def check_subtotals(p: PeriodData, refs: RefIndex) -> list[Alert]:
    alerts = []
    sums: dict[tuple[str, str], float] = defaultdict(float)
    for e in p.entries:
        key = (e["subcategory_id"], e["movement_type"])
        sums[key] += e["amount"]

    for sub in p.category_subtotals:
        key = (sub["subcategory_id"], sub["movement_type"])
        expected = sub["amount"]
        actual = sums.get(key, 0.0)
        if _approx_eq(actual, expected):
            continue
        sub_name = refs.subcategory_name(sub["subcategory_id"])
        cat_name = refs.category_name(sub["subcategory_id"])
        diff = actual - expected
        alerts.append(_alert(p.period, "subtotal_mismatch", "warning",
            f"Subtotal divergente: {sub_name} em {p.period}",
            f"'{sub_name}' ({cat_name}): soma lançamentos = R$ {actual:.2f}, "
            f"subtotal reportado = R$ {expected:.2f}. Diferença: R$ {diff:.2f}",
            {"subcategory": sub_name, "category": cat_name,
             "sum_entries": round(actual, 2), "reported": expected, "difference": round(diff, 2)},
            discriminator=sub["subcategory_id"],
        ))

    return alerts


def check_duplicates(p: PeriodData) -> list[Alert]:
    alerts = []
    seen: dict[tuple, list[dict]] = defaultdict(list)
    for e in p.entries:
        key = (e["date"], e["description"].strip().upper(), e["amount"], e["movement_type"])
        seen[key].append(e)

    for key, group in seen.items():
        if len(group) <= 1:
            continue
        date, desc, amount, mov_type = key
        alerts.append(_alert(p.period, "duplicate_entry", "warning",
            f"Lançamento duplicado em {p.period}",
            f"{len(group)}x '{desc}' em {date} com valor R$ {amount:.2f} ({mov_type})",
            {"date": date, "description": desc, "amount": amount,
             "movement_type": mov_type, "count": len(group),
             "entry_ids": [e["id"] for e in group]},
            discriminator=f"{date}:{desc}:{amount}",
        ))

    return alerts


def check_negative_credits(p: PeriodData) -> list[Alert]:
    negatives = [e for e in p.credit_entries if e["amount"] < 0]
    if not negatives:
        return []
    total = sum(e["amount"] for e in negatives)
    return [_alert(p.period, "negative_credit", "warning",
        f"{len(negatives)} receita(s) com valor negativo em {p.period}",
        f"{len(negatives)} lançamentos tipo C com valor < 0, totalizando R$ {total:.2f}.",
        {"count": len(negatives), "total": round(total, 2),
         "entry_ids": [e["id"] for e in negatives]},
    )]


def check_missing_periods(p: PeriodData, all_periods: dict[str, PeriodData]) -> list[Alert]:
    sorted_keys = sorted(all_periods.keys())
    idx = sorted_keys.index(p.period)
    if idx == 0:
        return []
    prev_period = sorted_keys[idx - 1]

    def _next_month(periodo: str) -> str:
        y, m = int(periodo[:4]), int(periodo[5:])
        m += 1
        if m > 12:
            m, y = 1, y + 1
        return f"{y:04d}-{m:02d}"

    expected = _next_month(prev_period)
    if expected == p.period:
        return []

    missing = []
    cur = expected
    while cur < p.period:
        missing.append(cur)
        cur = _next_month(cur)

    return [_alert(p.period, "missing_period", "critical",
        f"{len(missing)} período(s) ausente(s) antes de {p.period}",
        f"Período(s) ausente(s) entre {prev_period} e {p.period}: {', '.join(missing)}",
        {"prev_period": prev_period, "missing": missing},
    )]


def check_large_expenses_no_document(p: PeriodData) -> list[Alert]:
    entry_ids_with_docs = p.entry_ids_with_documents
    no_doc = [e for e in p.debit_entries
              if e["amount"] >= 1000 and e["id"] not in entry_ids_with_docs]
    if not no_doc:
        return []
    total = sum(e["amount"] for e in no_doc)
    return [_alert(p.period, "large_expense_no_document", "info",
        f"{len(no_doc)} despesa(s) ≥ R$1.000 sem comprovante em {p.period}",
        f"{len(no_doc)} lançamentos de despesa ≥ R$1.000 sem documento anexo, "
        f"totalizando R$ {total:.2f}.",
        {"count": len(no_doc), "total": round(total, 2),
         "entry_ids": [e["id"] for e in no_doc]},
    )]


def check_new_vendors(p: PeriodData, refs: RefIndex) -> list[Alert]:
    alerts = []
    vendor_totals: dict[str, float] = defaultdict(float)
    for e in p.entries:
        if e.get("vendor_id"):
            vendor_totals[e["vendor_id"]] += e["amount"]

    for vendor_id, total in vendor_totals.items():
        if refs.vendor_first_seen.get(vendor_id) == p.period:
            name = refs.vendor_name(vendor_id)
            alerts.append(_alert(p.period, "new_vendor", "info",
                f"Fornecedor novo: {name} em {p.period}",
                f"'{name}' aparece pela primeira vez neste período, "
                f"com R$ {total:.2f} em despesas.",
                {"vendor_id": vendor_id, "vendor_name": name, "total": round(total, 2)},
                discriminator=vendor_id,
            ))

    return alerts


def run_consistency(
    period: PeriodData,
    all_periods: dict[str, PeriodData],
    refs: RefIndex,
) -> list[Alert]:
    alerts = []
    alerts.extend(check_balance_month(period))
    alerts.extend(check_balance_accumulated(period))
    alerts.extend(check_balance_continuity(period, all_periods))
    alerts.extend(check_entries_vs_totals(period))
    alerts.extend(check_subtotals(period, refs))
    alerts.extend(check_duplicates(period))
    alerts.extend(check_negative_credits(period))
    alerts.extend(check_missing_periods(period, all_periods))
    alerts.extend(check_large_expenses_no_document(period))
    alerts.extend(check_new_vendors(period, refs))

    logger.info("Consistency %s: %d alerts", period.period, len(alerts))
    return alerts
