"""Materialize a period's page images from R2 into the ephemeral local cache.

Claude vision (`classify-doc-page`) Reads a local file path and the legacy content-hash
fallback hashes raw page bytes — neither can operate on an R2 key. This module downloads
the in-scope page images from R2 to a git-ignored cache dir and **rewrites the in-memory
``attachments[].file_path``** to the local cache paths, so the docs-plan ``read_path``s,
the page-refs in the mismatch summary, the content-hash fallback/backfill, and the
extraction provider all transparently use local files — exactly as they did when the
scraper wrote images to disk. The image cache is scratch (reproducible from R2).

The only write-back to D1 is the best-effort ``content_hash`` backfill for attachments
captured before that column existed (feature 016); page images themselves are never
written back.
"""

import logging
from pathlib import Path

from common import d1
from common.d1 import Target
from common.hashing import content_hash

logger = logging.getLogger(__name__)


def _split_tokens(file_path: str | None) -> list[str]:
    return [t.strip() for t in (file_path or "").split(";") if t.strip()]


def _backfill_content_hashes(updates: list[tuple[str, str]], target: Target) -> None:
    """Best-effort UPDATE of ``attachments.content_hash`` for rows captured pre-016.

    Writes only the ``content_hash`` column, only where it is still NULL (so a value
    written by a concurrent scrape is never clobbered), and never touches any other
    column. A failure is logged and swallowed — grouping already used the in-memory hash
    this run, so the backfill is a convergence optimization, not a correctness dependency.
    """
    if not updates:
        return
    stmts = []
    for doc_id, h in updates:
        did = doc_id.replace("'", "''")
        hh = h.replace("'", "''")
        stmts.append(f"UPDATE attachments SET content_hash = '{hh}' WHERE id = '{did}' AND content_hash IS NULL;")
    try:
        d1.execute_sql("\n".join(stmts), target=target)
        logger.info("Backfilled content_hash for %d attachment(s)", len(updates))
    except Exception as e:  # noqa: BLE001 — best-effort; never abort analysis on backfill failure
        logger.warning("content_hash backfill failed (%d row(s)); continuing: %s", len(updates), e)


def attachments_needing_hash_backfill(
    periods: dict,
    attachment_ids: list[str] | None = None,
) -> list[str]:
    """Return the in-scope attachment ids that genuinely need an image fetch for a backfill.

    The only reason ``apply-extractions`` still touches R2 is to hash the attachments whose
    ``content_hash`` column is empty (legacy rows, or a future page-bearing row that ever
    lands without a hash) — grouping reads the stored column for everything else. An
    attachment qualifies iff it is **page-bearing** (non-empty ``file_path``) **and** has a
    falsy ``content_hash``. A page-less attachment (empty ``file_path``) is never returned:
    it has no hash by nature, groups as a singleton, and has nothing to materialize.

    Pure read of the in-memory ``periods`` (no D1/R2, no mutation). When ``attachment_ids``
    is given, only those ids are considered. Returns ids in deterministic iteration order.
    """
    scope = set(attachment_ids) if attachment_ids else None
    needing: list[str] = []
    for pd in periods.values():
        for doc in pd.attachments:
            if scope is not None and doc["id"] not in scope:
                continue
            if not _split_tokens(doc.get("file_path")):
                continue  # page-less: not hashable, never work
            if not doc.get("content_hash"):
                needing.append(doc["id"])
    return needing


def materialize_period_images(
    periods: dict,
    cache_dir: str,
    target: Target,
    *,
    attachment_ids: list[str] | None = None,
    backfill_hash: bool = True,
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

    When ``backfill_hash`` is set (default), any attachment whose ``content_hash`` column
    is empty (data captured before feature 016) gets the hash computed from its now-local
    pages, mutated in memory (so grouping this run reads it) and written back to D1
    best-effort, so subsequent runs group purely from the stored column.
    """
    cache_root = Path(cache_dir)
    scope = set(attachment_ids) if attachment_ids else None
    downloaded = 0
    hash_updates: list[tuple[str, str]] = []

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

            # Lazily fill the grouping key for rows captured before the column existed.
            if backfill_hash and not doc.get("content_hash"):
                h = content_hash(doc["file_path"])
                if h:
                    doc["content_hash"] = h
                    hash_updates.append((doc["id"], h))

    if downloaded:
        logger.info("Materialized %d page image(s) from R2 into %s", downloaded, cache_dir)
    if backfill_hash:
        _backfill_content_hashes(hash_updates, target)
    return downloaded
