import logging
import re

from playwright.async_api import Page

from ..config import SELECTORS

logger = logging.getLogger(__name__)


def parse_brl(text: str) -> float:
    """Convert 'R$ 443.995,17' or '443.995,17' to 443995.17."""
    cleaned = re.sub(r"[R$\s]", "", text)
    cleaned = cleaned.replace(".", "").replace(",", ".")
    return float(cleaned)


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
        value = parse_brl((await value_el.inner_text()).strip())

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
