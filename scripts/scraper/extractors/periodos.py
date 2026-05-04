import logging
import re

from playwright.async_api import Page

from ..config import SELECTORS

logger = logging.getLogger(__name__)

MONTH_MAP = {
    "JANEIRO": "01",
    "FEVEREIRO": "02",
    "MARÇO": "03",
    "ABRIL": "04",
    "MAIO": "05",
    "JUNHO": "06",
    "JULHO": "07",
    "AGOSTO": "08",
    "SETEMBRO": "09",
    "OUTUBRO": "10",
    "NOVEMBRO": "11",
    "DEZEMBRO": "12",
}


def parse_periodo(text: str) -> str:
    """Convert 'JANEIRO DE 2026' to '2026-01'."""
    match = re.match(r"(\w+)\s+DE\s+(\d{4})", text.strip())
    if not match:
        raise ValueError(f"Cannot parse period: {text}")
    month_name, year = match.groups()
    month_num = MONTH_MAP.get(month_name.upper())
    if not month_num:
        raise ValueError(f"Unknown month: {month_name}")
    return f"{year}-{month_num}"


async def list_periodos(page: Page) -> list[dict]:
    """Extract all available periods from the select dropdown.

    Returns list of dicts: [{"book_id": 18621003, "label": "JANEIRO DE 2026", "periodo": "2026-01"}, ...]
    """
    options = await page.query_selector_all(SELECTORS["period_options"])
    periodos = []
    for option in options:
        value = await option.get_attribute("value")
        label = (await option.inner_text()).strip()
        if not value or not label:
            continue
        periodo = parse_periodo(label)
        periodos.append({
            "book_id": int(value),
            "label": label,
            "periodo": periodo,
        })
    logger.info("Found %d periods available", len(periodos))
    return periodos
