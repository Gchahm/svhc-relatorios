import logging

from playwright.async_api import Browser, BrowserContext, Page, async_playwright

from .config import (
    BRCONDOS_PASSWORD,
    BRCONDOS_URL,
    BRCONDOS_USER,
    HEADLESS,
    LOGIN_PATH,
    SELECTORS,
)

logger = logging.getLogger(__name__)


class BRCondosBrowser:
    """Manages Playwright browser instance and authentication with BRCondos portal."""

    def __init__(self) -> None:
        self._playwright = None
        self._browser: Browser | None = None
        self._context: BrowserContext | None = None
        self.page: Page | None = None

    async def start(self) -> None:
        self._playwright = await async_playwright().start()
        self._browser = await self._playwright.chromium.launch(headless=HEADLESS)
        self._context = await self._browser.new_context()
        self.page = await self._context.new_page()
        logger.info("Browser started")

    async def login(self) -> None:
        if not self.page:
            raise RuntimeError("Browser not started. Call start() first.")

        url = f"{BRCONDOS_URL}{LOGIN_PATH}"
        logger.info("Navigating to login page: %s", url)
        await self.page.goto(url, wait_until="networkidle")

        await self.page.fill(SELECTORS["login_user"], BRCONDOS_USER)
        await self.page.fill(SELECTORS["login_password"], BRCONDOS_PASSWORD)

        async with self.page.expect_navigation(wait_until="networkidle"):
            await self.page.click(SELECTORS["login_submit"])

        logger.info("Login completed. Current URL: %s", self.page.url)

    async def navigate_to_accountability(self, book_id: int | None = None) -> None:
        if not self.page:
            raise RuntimeError("Browser not started.")

        from .config import ACCOUNTABILITY_PATH

        url = f"{BRCONDOS_URL}{ACCOUNTABILITY_PATH}"
        if book_id:
            url += f"?q={book_id}&list=true"
        logger.info("Navigating to: %s", url)
        await self.page.goto(url, wait_until="networkidle")

    async def screenshot(self, path: str) -> None:
        if self.page:
            await self.page.screenshot(path=path)
            logger.info("Screenshot saved to %s", path)

    async def close(self) -> None:
        if self._browser:
            await self._browser.close()
        if self._playwright:
            await self._playwright.stop()
        logger.info("Browser closed")
