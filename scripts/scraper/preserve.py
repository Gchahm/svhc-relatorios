"""Preservation of scraper-owned attachment columns across re-scrapes (BUG-001 / issue #32).

The scraper upserts attachment rows via ``INSERT OR REPLACE`` (delete-then-insert), so any column
absent/NULL in the written row reverts to its schema default. ``file_path`` (R2-key linkage) and
``content_hash`` (shared-NF grouping key) are produced only on a successful in-run image download;
on a re-scrape that omits or fails the download they would be reset to NULL even though the page
images still exist in R2 and nothing about the attachment changed. This module holds the pure merge
that carries the existing D1 values onto the freshly-scraped rows when the run produced nothing
newer.

Kept stdlib-only and free of the scraper's playwright import so it is unit-testable directly (see
``scripts/tests/test_attachment_preserve.py``), mirroring how the analysis pipeline isolates its
pure seams.
"""

from __future__ import annotations

# Scraper-owned attachment columns that are produced only on a successful in-run image download
# (NULL otherwise) and must therefore survive a re-scrape that did not (re)download the pages.
PRESERVABLE_ATTACHMENT_COLS = ("file_path", "content_hash")


def preserve_existing_attachment_cols(
    attachments_out: list[dict],
    existing_by_id: dict[str, dict],
) -> None:
    """Fill NULL ``file_path``/``content_hash`` on freshly-scraped attachment rows from D1.

    Mutates ``attachments_out`` in place. For each row, for each preservable column: if the row's
    freshly-scraped value is falsy (None / empty — i.e. this run did not (re)download the pages) AND
    ``existing_by_id`` holds a non-falsy value for that row's id, copy the existing value onto the
    row. A non-falsy fresh value (a successful in-run download) is left untouched, so it overwrites
    the prior value on upsert (US2). Each column is decided independently, per attachment id (US1
    partial-download case); rows whose id is absent from ``existing_by_id`` (first scrape / new
    attachment) pass through unchanged. ``id``/``entry_id``/``external_document_id`` are never
    touched. The analysis-owned ``attachment_state`` table is neither read nor written here.
    """
    if not existing_by_id:
        return
    for row in attachments_out:
        existing = existing_by_id.get(row.get("id"))
        if not existing:
            continue
        for col in PRESERVABLE_ATTACHMENT_COLS:
            if not row.get(col) and existing.get(col):
                row[col] = existing[col]
