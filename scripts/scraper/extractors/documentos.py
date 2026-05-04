import logging
import pathlib
import re
from urllib.parse import urlparse

from playwright.async_api import Page

from ..config import BRCONDOS_URL

logger = logging.getLogger(__name__)

DATA_DIR = pathlib.Path("data/documentos")


def _build_doc_path(periodo: str, brcondos_id: int, filename: str) -> pathlib.Path:
    """Build local path: data/documentos/{ano}/{mes}/{brcondos_id}_{filename}."""
    year, month = periodo.split("-")
    directory = DATA_DIR / year / month
    safe_name = re.sub(r'[^\w.\-]', '_', filename)
    return directory / f"{brcondos_id}_{safe_name}"


def _extension_from_url(url: str) -> str:
    """Extract file extension from a URL, ignoring query params."""
    path = urlparse(url).path
    ext = pathlib.Path(path).suffix
    return ext if ext else ".png"


async def download_documento(
    page: Page, brcondos_document_id: int, periodo: str
) -> str | None:
    """Download a document from BRCondos and return the local file path.

    Returns None if download fails.
    """
    url = f"{BRCONDOS_URL}/Dashboard/ViewDocuments/{brcondos_document_id}"
    logger.info("Downloading document %d from %s", brcondos_document_id, url)

    doc_page = None
    try:
        doc_page = await page.context.new_page()
        await doc_page.goto(url, wait_until="networkidle", timeout=60000)

        image_urls = await doc_page.evaluate("""() => {
            const imgs = document.querySelectorAll('.unic-image-container img, img.responsive-image');
            if (imgs.length > 0) {
                return Array.from(imgs).map(img => img.src).filter(s => s && s.startsWith('http'));
            }
            const allImgs = document.querySelectorAll('img[src*="s3."]');
            return Array.from(allImgs).map(img => img.src).filter(s => s && s.startsWith('http'));
        }""")

        if not image_urls:
            dest = _build_doc_path(periodo, brcondos_document_id, "screenshot.png")
            dest.parent.mkdir(parents=True, exist_ok=True)
            await doc_page.screenshot(path=str(dest), full_page=True)
            await doc_page.close()
            logger.info(
                "No images found for doc %d, saved screenshot to %s",
                brcondos_document_id, dest,
            )
            return str(dest)

        saved_paths = []
        for i, img_url in enumerate(image_urls):
            ext = _extension_from_url(img_url)
            suffix = f"_p{i + 1}" if len(image_urls) > 1 else ""
            dest = _build_doc_path(
                periodo, brcondos_document_id, f"doc{suffix}{ext}"
            )
            dest.parent.mkdir(parents=True, exist_ok=True)

            response = await doc_page.context.request.get(img_url)
            if response.ok:
                content = await response.body()
                dest.write_bytes(content)
                saved_paths.append(str(dest))
                logger.debug(
                    "  Saved page %d/%d (%d bytes) to %s",
                    i + 1, len(image_urls), len(content), dest,
                )
            else:
                logger.warning(
                    "  Failed to fetch image %d for doc %d: HTTP %d",
                    i + 1, brcondos_document_id, response.status,
                )

        await doc_page.close()

        if saved_paths:
            result = saved_paths[0] if len(saved_paths) == 1 else ";".join(saved_paths)
            logger.info(
                "Document %d: saved %d page(s) to %s",
                brcondos_document_id, len(saved_paths), saved_paths[0],
            )
            return result

        return None

    except Exception as e:
        logger.warning("Failed to download document %d: %s", brcondos_document_id, e)
        if doc_page:
            try:
                await doc_page.close()
            except Exception:
                pass
        return None


async def download_all_documentos(
    page: Page, documentos: list[dict], periodo: str
) -> dict[int, str]:
    """Download all documents for a period.

    Args:
        page: Playwright page (used for browser context).
        documentos: list of {"lancamento_id": int, "brcondos_document_id": int}.
        periodo: "YYYY-MM" for organizing files.

    Returns:
        dict mapping brcondos_document_id -> local file path.
    """
    results = {}
    seen = set()

    for doc in documentos:
        doc_id = doc["brcondos_document_id"]
        if doc_id in seen:
            continue
        seen.add(doc_id)

        path = await download_documento(page, doc_id, periodo)
        if path:
            results[doc_id] = path

    logger.info(
        "Downloaded %d/%d unique documents for period %s",
        len(results),
        len(seen),
        periodo,
    )
    return results
