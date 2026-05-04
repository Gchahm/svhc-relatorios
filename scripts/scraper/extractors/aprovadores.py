import logging

from playwright.async_api import Page

logger = logging.getLogger(__name__)


async def extract_aprovadores(page: Page) -> list[dict]:
    """Extract approvers list and their status from the overview tab."""
    container = await page.query_selector(".prescontas-overview-aprovadores")
    if not container:
        logger.warning("Aprovadores section not found")
        return []

    items = await container.query_selector_all(".container-box-content")
    aprovadores = []
    for item in items:
        nome_el = await item.query_selector(".font-size-0_86rem.font-weight-500")
        status_el = await item.query_selector(".text-uppercase.font-size-0_86rem")
        if nome_el and status_el:
            nome = (await nome_el.inner_text()).strip()
            status = (await status_el.inner_text()).strip()
            if nome:
                aprovadores.append({"nome": nome, "status": status})

    logger.info("Found %d aprovadores", len(aprovadores))
    return aprovadores
