import logging
from pathlib import Path
from urllib.parse import urlparse

from playwright.async_api import Page

from ..config import BRCONDOS_URL

logger = logging.getLogger(__name__)


def _extension_from_url(url: str) -> str:
    """Extract file extension from a URL, ignoring query params."""
    path = urlparse(url).path
    ext = Path(path).suffix
    return ext if ext else ".png"


async def _download_single_document(
    page: Page,
    brcondos_document_id: int,
    dest_dir: Path,
    base_name: str,
    doc_index: int | None = None,
) -> list[str]:
    """Download a single document (which may have multiple pages/images).

    Returns list of saved file paths.
    """
    url = f"{BRCONDOS_URL}/Dashboard/ViewDocuments/{brcondos_document_id}"
    logger.info("Downloading document %d from %s", brcondos_document_id, url)

    suffix = f"_doc{doc_index}" if doc_index is not None else ""
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
            dest = dest_dir / f"{base_name}{suffix}.png"
            dest.parent.mkdir(parents=True, exist_ok=True)
            await doc_page.screenshot(path=str(dest), full_page=True)
            await doc_page.close()
            logger.info("No images found for doc %d, saved screenshot to %s", brcondos_document_id, dest)
            return [str(dest)]

        saved = []
        for i, img_url in enumerate(image_urls):
            ext = _extension_from_url(img_url)
            page_suffix = f"_p{i + 1}" if len(image_urls) > 1 else ""
            dest = dest_dir / f"{base_name}{suffix}{page_suffix}{ext}"
            dest.parent.mkdir(parents=True, exist_ok=True)

            response = await doc_page.context.request.get(img_url)
            if response.ok:
                content = await response.body()
                dest.write_bytes(content)
                saved.append(str(dest))
                logger.debug("  Saved page %d/%d (%d bytes) to %s", i + 1, len(image_urls), len(content), dest)
            else:
                logger.warning("  Failed to fetch image %d for doc %d: HTTP %d", i + 1, brcondos_document_id, response.status)

        await doc_page.close()
        return saved

    except Exception as e:
        logger.warning("Failed to download document %d: %s", brcondos_document_id, e)
        if doc_page:
            try:
                await doc_page.close()
            except Exception:
                pass
        return []


async def download_entry_documents(
    page: Page,
    documento_ids: list[int],
    entry_id: str,
    dest_dir: Path,
) -> dict[int, list[str]]:
    """Download all documents for a single entry.

    Files are named by entry_id so they can be matched back.

    Returns:
        dict mapping brcondos_document_id -> list of local file paths.
    """
    base_name = entry_id
    results: dict[int, list[str]] = {}

    for i, doc_id in enumerate(documento_ids):
        doc_index = i + 1 if len(documento_ids) > 1 else None
        paths = await _download_single_document(page, doc_id, dest_dir, base_name, doc_index)
        if paths:
            results[doc_id] = paths

    return results
