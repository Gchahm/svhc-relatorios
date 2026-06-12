import logging
import math
import re

from playwright.async_api import Page

from ..config import SELECTORS

logger = logging.getLogger(__name__)


def parse_brl(text: str) -> float | None:
    """Convert 'R$ 443.995,17' or '443.995,17' to 443995.17.

    Tolerant + pure (no logging/I/O): returns ``None`` for any input that does not yield a finite
    number — empty/whitespace-only, junk, or a value that parses to NaN/inf. Never raises for a
    ``str`` input, so callers decide severity (skip the row vs. fail the period). Feature 030 /
    IMP-001: a malformed ledger cell must fail its row, not abort the whole period.
    """
    if text is None:
        return None
    cleaned = re.sub(r"[R$\s]", "", text)
    cleaned = cleaned.replace(".", "").replace(",", ".")
    if not cleaned:
        return None
    try:
        value = float(cleaned)
    except (ValueError, TypeError):
        return None
    if not math.isfinite(value):
        return None
    return value


async def extract_demonstrativo(page: Page) -> dict:
    """Extract financial summary from the overview tab.

    Returns dict with keys: total_receitas, total_despesas, saldo_inicial, saldo_mes, saldo_acumulado.
    """
    tab = await page.query_selector(SELECTORS["tab_overview"])
    if not tab:
        raise RuntimeError("Overview tab not found")

    dem_fin = await tab.query_selector(".prescontas-demonstrativo-financeiro")
    if not dem_fin:
        raise RuntimeError("Demonstrativo financeiro section not found")

    values = await dem_fin.query_selector_all(".dem-fin-box-value")
    titles = await dem_fin.query_selector_all(".dem-fin-box-title")

    data = {}
    for title_el, value_el in zip(titles, values):
        title = (await title_el.inner_text()).strip()
        raw_value = (await value_el.inner_text()).strip()
        value = parse_brl(raw_value)
        # The 5 demonstrativo summary values are REQUIRED for the period's report row; a malformed
        # one is genuinely fatal for the period (preserves the existing "Missing financial data"
        # abort semantics) — unlike a per-row ledger cell, which fails only its row.
        if value is None:
            raise RuntimeError(f"Unparseable demonstrativo value for {title!r}: {raw_value!r}")

        if "Receitas" in title:
            data["total_receitas"] = value
        elif "Despesas" in title:
            data["total_despesas"] = value
        elif "Saldo Inicial" in title:
            data["saldo_inicial"] = value
        elif "Saldo do Mês" in title or "Saldo do Mes" in title:
            data["saldo_mes"] = value
        elif "Saldo Acumulado" in title:
            data["saldo_acumulado"] = value

    expected_keys = [
        "total_receitas",
        "total_despesas",
        "saldo_inicial",
        "saldo_mes",
        "saldo_acumulado",
    ]
    missing = [k for k in expected_keys if k not in data]
    if missing:
        raise RuntimeError(f"Missing financial data: {missing}")

    logger.info(
        "Demonstrativo: receitas=%.2f despesas=%.2f saldo_acumulado=%.2f",
        data["total_receitas"],
        data["total_despesas"],
        data["saldo_acumulado"],
    )
    return data
