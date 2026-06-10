"""Materialize a period's page images from R2 into the ephemeral local cache.

Claude vision (`classify-doc-page`) Reads a local file path and NF grouping
(`nf_groups.content_hash`) hashes raw page bytes — neither can operate on an R2
key. This module downloads the in-scope page images from R2 to a git-ignored cache
dir and **rewrites the in-memory ``attachments[].file_path``** to the local cache
paths, so ``content_hash``, the docs-plan manifest read_paths, the page-refs in the
mismatch summary, and the extraction provider all transparently use local files —
exactly as they did when the scraper wrote images to disk. The cache is scratch
(reproducible from R2) and never written back to D1.
"""

import logging
from pathlib import Path

from common import d1
from common.d1 import Target

logger = logging.getLogger(__name__)


def _split_tokens(file_path: str | None) -> list[str]:
    return [t.strip() for t in (file_path or "").split(";") if t.strip()]


def materialize_period_images(
    periods: dict,
    cache_dir: str,
    target: Target,
    *,
    attachment_ids: list[str] | None = None,
) -> int:
    """Ensure each attachment's page images are present in the cache; rewrite file_path.

    For every attachment (optionally scoped to ``attachment_ids``) whose ``file_path``
    holds R2-key tokens (``<period>/<basename>``), download any missing page from R2
    into ``<cache_dir>/<key>`` and rewrite the attachment's ``file_path`` to the
    ``;``-joined local cache paths. Already-cached pages (and attachments already
    pointing at existing local files) are skipped, so repeated commands in a loop are
    cheap. Returns the number of pages downloaded this call.

    Mutates the attachments in place; since ``PeriodData.attachments`` and
    ``raw["attachments"]`` are the same list, all readers see the cache paths.
    """
    cache_root = Path(cache_dir)
    scope = set(attachment_ids) if attachment_ids else None
    downloaded = 0

    for pd in periods.values():
        for doc in pd.attachments:
            if scope is not None and doc["id"] not in scope:
                continue
            tokens = _split_tokens(doc.get("file_path"))
            if not tokens:
                continue
            local_paths: list[str] = []
            for token in tokens:
                # A token already pointing at an existing local file (e.g. left by a
                # scrape run in this same cache) is used as-is.
                if Path(token).exists():
                    local_paths.append(token)
                    continue
                dest = cache_root / token  # token is the R2 key: <period>/<basename>
                if not dest.exists():
                    if d1.get_object(token, str(dest), target=target):
                        downloaded += 1
                    else:
                        logger.warning("Missing R2 object for key %s (attachment %s)", token, doc["id"])
                        # Keep the token so a downstream read records a clean page-error.
                        local_paths.append(token)
                        continue
                local_paths.append(str(dest))
            doc["file_path"] = ";".join(local_paths)

    if downloaded:
        logger.info("Materialized %d page image(s) from R2 into %s", downloaded, cache_dir)
    return downloaded
