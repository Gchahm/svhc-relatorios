"""Tests for scraper-owned attachment column preservation across re-scrapes (BUG-001 / issue #32).

The scraper upserts attachment rows via INSERT OR REPLACE, which would reset the scraper-owned
``file_path``/``content_hash`` to NULL on a re-scrape that did not (re)download the pages. The pure
``preserve_existing_attachment_cols`` merge carries the existing D1 values onto the freshly-scraped
rows when the run produced nothing newer. Covers (per the spec's user stories):

- US1 — refresh without re-download preserves existing values (FR-001/002, SC-001), decided per
  attachment id so a partial download preserves the un-downloaded siblings (FR-004).
- US2 — a successful in-run download supplies fresh values that win (FR-003, SC-002).
- US3 — first scrape (no existing row) is unaffected (FR-007, SC-004).
- Invariant — id/entry_id/external_document_id are never mutated (FR-006).

Run: ``python -m unittest discover -s scripts/tests -t scripts``
"""

import unittest

from scraper.preserve import PRESERVABLE_ATTACHMENT_COLS, preserve_existing_attachment_cols


def _row(aid, entry_id, *, file_path=None, content_hash=None):
    """A freshly-scraped attachment row as runner.py builds it (linkage cols NULL by default)."""
    return {
        "id": aid,
        "entry_id": entry_id,
        "external_document_id": 1000 + int(aid.rsplit("-", 1)[-1]),
        "file_path": file_path,
        "content_hash": content_hash,
    }


def _existing(file_path=None, content_hash=None):
    return {"file_path": file_path, "content_hash": content_hash}


class PreserveOnReScrapeTest(unittest.TestCase):
    """US1 — refresh without re-downloading images keeps existing values."""

    def test_null_fresh_values_inherit_existing(self):
        rows = [_row("att-1", "ent-1")]  # fresh row: both NULL (no download this run)
        existing = {"att-1": _existing(file_path="2025-12/ent-1_p1.png", content_hash="hash-1")}
        preserve_existing_attachment_cols(rows, existing)
        self.assertEqual(rows[0]["file_path"], "2025-12/ent-1_p1.png")
        self.assertEqual(rows[0]["content_hash"], "hash-1")

    def test_failed_download_preserves(self):
        # A download failure leaves the fresh row's values NULL — same as no-download.
        rows = [_row("att-1", "ent-1", file_path=None, content_hash=None)]
        existing = {"att-1": _existing(file_path="2025-12/ent-1_p1.png", content_hash="hash-1")}
        preserve_existing_attachment_cols(rows, existing)
        self.assertEqual(rows[0]["file_path"], "2025-12/ent-1_p1.png")
        self.assertEqual(rows[0]["content_hash"], "hash-1")

    def test_per_id_partial_download(self):
        # att-1 downloaded fresh this run; att-2 did not — each decided independently (FR-004).
        rows = [
            _row("att-1", "ent-1", file_path="2025-12/ent-1_NEW.png", content_hash="new-1"),
            _row("att-2", "ent-2"),
        ]
        existing = {
            "att-1": _existing(file_path="2025-12/ent-1_OLD.png", content_hash="old-1"),
            "att-2": _existing(file_path="2025-12/ent-2_p1.png", content_hash="hash-2"),
        }
        preserve_existing_attachment_cols(rows, existing)
        # att-1 fresh values win
        self.assertEqual(rows[0]["file_path"], "2025-12/ent-1_NEW.png")
        self.assertEqual(rows[0]["content_hash"], "new-1")
        # att-2 existing values preserved
        self.assertEqual(rows[1]["file_path"], "2025-12/ent-2_p1.png")
        self.assertEqual(rows[1]["content_hash"], "hash-2")

    def test_independent_columns(self):
        # file_path downloaded fresh, content_hash NULL → preserve only content_hash.
        rows = [_row("att-1", "ent-1", file_path="2025-12/ent-1_NEW.png", content_hash=None)]
        existing = {"att-1": _existing(file_path="2025-12/ent-1_OLD.png", content_hash="old-1")}
        preserve_existing_attachment_cols(rows, existing)
        self.assertEqual(rows[0]["file_path"], "2025-12/ent-1_NEW.png")  # fresh wins
        self.assertEqual(rows[0]["content_hash"], "old-1")  # preserved

    def test_prior_null_and_fresh_null_stays_null(self):
        rows = [_row("att-1", "ent-1")]
        existing = {"att-1": _existing(file_path=None, content_hash=None)}
        preserve_existing_attachment_cols(rows, existing)
        self.assertIsNone(rows[0]["file_path"])
        self.assertIsNone(rows[0]["content_hash"])

    def test_empty_string_file_path_is_treated_as_absent(self):
        # Defensive: an empty file_path would itself be a loss; preserve over it.
        rows = [_row("att-1", "ent-1", file_path="")]
        existing = {"att-1": _existing(file_path="2025-12/ent-1_p1.png", content_hash="hash-1")}
        preserve_existing_attachment_cols(rows, existing)
        self.assertEqual(rows[0]["file_path"], "2025-12/ent-1_p1.png")


class FreshDownloadWinsTest(unittest.TestCase):
    """US2 — a successful in-run download overwrites prior values."""

    def test_fresh_values_override_existing(self):
        rows = [_row("att-1", "ent-1", file_path="2025-12/ent-1_NEW.png", content_hash="new-1")]
        existing = {"att-1": _existing(file_path="2025-12/ent-1_OLD.png", content_hash="old-1")}
        preserve_existing_attachment_cols(rows, existing)
        self.assertEqual(rows[0]["file_path"], "2025-12/ent-1_NEW.png")
        self.assertEqual(rows[0]["content_hash"], "new-1")


class FirstScrapeUnaffectedTest(unittest.TestCase):
    """US3 — no pre-existing rows ⇒ behavior unchanged."""

    def test_empty_existing_map_is_noop_for_null(self):
        rows = [_row("att-1", "ent-1")]
        preserve_existing_attachment_cols(rows, {})
        self.assertIsNone(rows[0]["file_path"])
        self.assertIsNone(rows[0]["content_hash"])

    def test_empty_existing_map_keeps_downloaded_values(self):
        rows = [_row("att-1", "ent-1", file_path="2025-12/ent-1_p1.png", content_hash="hash-1")]
        preserve_existing_attachment_cols(rows, {})
        self.assertEqual(rows[0]["file_path"], "2025-12/ent-1_p1.png")
        self.assertEqual(rows[0]["content_hash"], "hash-1")

    def test_new_id_not_in_existing_map_unaffected(self):
        # Re-scrape introduces a brand-new attachment id; nothing to preserve.
        rows = [_row("att-9", "ent-9")]
        existing = {"att-1": _existing(file_path="2025-12/ent-1_p1.png", content_hash="hash-1")}
        preserve_existing_attachment_cols(rows, existing)
        self.assertIsNone(rows[0]["file_path"])
        self.assertIsNone(rows[0]["content_hash"])


class InvariantTest(unittest.TestCase):
    """FR-006 — mirror columns are never mutated; only the two linkage cols are preservable."""

    def test_mirror_columns_untouched(self):
        rows = [_row("att-1", "ent-1")]
        existing = {"att-1": _existing(file_path="2025-12/ent-1_p1.png", content_hash="hash-1")}
        preserve_existing_attachment_cols(rows, existing)
        self.assertEqual(rows[0]["id"], "att-1")
        self.assertEqual(rows[0]["entry_id"], "ent-1")
        self.assertEqual(rows[0]["external_document_id"], 1001)

    def test_only_two_preservable_columns(self):
        self.assertEqual(PRESERVABLE_ATTACHMENT_COLS, ("file_path", "content_hash"))


if __name__ == "__main__":
    unittest.main()
