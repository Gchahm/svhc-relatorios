import logging
import re
from datetime import date

from playwright.async_api import Page

from ..config import TAB_CATEGORIES
from .demonstrativo import parse_brl

logger = logging.getLogger(__name__)


def parse_date(text: str) -> date:
    """Convert 'DD/MM/YYYY' to date."""
    day, month, year = text.strip().split("/")
    return date(int(year), int(month), int(day))


async def extract_lancamentos_from_tab(
    page: Page, tab_id: str, categoria: str
) -> tuple[list[dict], list[dict]]:
    """Extract lancamentos and subtotals from a single tab.

    Returns (lancamentos, subtotais).
    """
    # The BRCondos HTML has malformed nesting — tab-pane divs are nested inside
    # each other because closing </div> tags are missing before <script> blocks.
    # We use JS DOM walking to get only THIS tab's table rows.
    rows_handle = await page.evaluate_handle(
        """(tabId) => {
            const tabs = document.querySelectorAll('#' + CSS.escape(tabId));
            for (const tab of tabs) {
                const tables = tab.querySelectorAll('table.prescontas-table');
                for (const t of tables) {
                    let el = t.parentElement;
                    let nested = false;
                    while (el && el !== tab) {
                        if (el.id && el.id.startsWith('tab_') && el.classList.contains('tab-pane')) {
                            nested = true;
                            break;
                        }
                        el = el.parentElement;
                    }
                    if (!nested) {
                        return Array.from(t.querySelectorAll('tbody tr'));
                    }
                }
            }
            return [];
        }""",
        tab_id,
    )

    rows_count = await rows_handle.evaluate("rows => rows.length")
    if rows_count == 0:
        logger.warning("Tab %s: no rows found, skipping", tab_id)
        return [], []

    lancamentos = []
    subtotais = []

    rows = []
    for i in range(rows_count):
        row_handle = await rows_handle.evaluate_handle(f"rows => rows[{i}]")
        rows.append(row_handle.as_element())

    for row in rows:
        classes = await row.get_attribute("class") or ""
        group_id = await row.get_attribute("data-group-id") or ""

        if "prescontas-table-title-row" in classes:
            tds = await row.query_selector_all("td")
            if len(tds) >= 4:
                subcategoria = group_id or (await tds[0].inner_text()).strip()
                valor_text = (await tds[2].inner_text()).strip()
                tipo_text = (await tds[3].inner_text()).strip() if len(tds) > 3 else ""

                if valor_text:
                    subtotais.append({
                        "categoria": categoria,
                        "subcategoria": subcategoria,
                        "valor": parse_brl(valor_text),
                        "tipo_movimento": tipo_text.strip() if tipo_text.strip() in ("D", "C") else "D",
                    })
        elif group_id:
            tds = await row.query_selector_all("td")
            if len(tds) < 5:
                continue

            date_el = await tds[0].query_selector("span")
            date_text = (await date_el.inner_text()).strip() if date_el else ""
            if not date_text:
                continue

            descricao = (await tds[1].inner_text()).strip()

            valor_el = await tds[3].query_selector(".font-size-1_1rem")
            valor_text = (await valor_el.inner_text()).strip() if valor_el else ""
            if not valor_text:
                continue

            tipo_el = await tds[4].query_selector(".font-weight-700, .font-weight-600")
            tipo_text = (await tipo_el.inner_text()).strip() if tipo_el else "D"

            doc_links = await row.query_selector_all('a[href*="/Dashboard/ViewDocuments/"]')
            documento_ids = []
            for doc_link in doc_links:
                href = await doc_link.get_attribute("href")
                if href:
                    match = re.search(r"/ViewDocuments/(\d+)", href)
                    if match:
                        doc_id = int(match.group(1))
                        if doc_id not in documento_ids:
                            documento_ids.append(doc_id)

            lancamentos.append({
                "data": parse_date(date_text),
                "descricao": descricao,
                "valor": parse_brl(valor_text),
                "tipo_movimento": tipo_text if tipo_text in ("D", "C") else "D",
                "categoria": categoria,
                "subcategoria": group_id,
                "documento_ids": documento_ids,
            })

    logger.info(
        "Tab %s (%s): %d lancamentos, %d subtotais",
        tab_id,
        categoria,
        len(lancamentos),
        len(subtotais),
    )
    return lancamentos, subtotais


async def extract_all_lancamentos(page: Page) -> tuple[list[dict], list[dict]]:
    """Extract lancamentos and subtotals from all category tabs.

    Returns (all_lancamentos, all_subtotais).
    """
    all_lancamentos = []
    all_subtotais = []

    for tab_id, categoria in TAB_CATEGORIES.items():
        lancamentos, subtotais = await extract_lancamentos_from_tab(
            page, tab_id, categoria
        )
        all_lancamentos.extend(lancamentos)
        all_subtotais.extend(subtotais)

    logger.info(
        "Total: %d lancamentos, %d subtotais",
        len(all_lancamentos),
        len(all_subtotais),
    )
    return all_lancamentos, all_subtotais
