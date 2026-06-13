"""Tests for the pure helpers in analysis.images and analysis.loader (TEST-002 / issue #69)."""

import unittest

from analysis.images import _split_tokens, attachments_needing_hash_backfill
from analysis.loader import _in_clause, _sql_str

from tests._fixtures import attachment, make_period


class SplitTokensTest(unittest.TestCase):
    def test_splits_and_strips(self):
        self.assertEqual(_split_tokens("a/b.png ; c/d.png"), ["a/b.png", "c/d.png"])

    def test_empty(self):
        self.assertEqual(_split_tokens(None), [])
        self.assertEqual(_split_tokens(""), [])


class NeedingHashBackfillTest(unittest.TestCase):
    def test_page_bearing_without_hash_qualifies(self):
        a1 = attachment("a1", "e1", file_path="2025-12/a1_p1.png", content_hash=None)
        a2 = attachment("a2", "e2", file_path="2025-12/a2_p1.png", content_hash="H")  # has hash
        a3 = attachment("a3", "e3", file_path="", content_hash=None)  # page-less
        pd = make_period("2025-12", attachments=[a1, a2, a3])
        self.assertEqual(attachments_needing_hash_backfill({"2025-12": pd}), ["a1"])

    def test_scope_filter(self):
        a1 = attachment("a1", "e1", file_path="2025-12/a1_p1.png", content_hash=None)
        a2 = attachment("a2", "e2", file_path="2025-12/a2_p1.png", content_hash=None)
        pd = make_period("2025-12", attachments=[a1, a2])
        self.assertEqual(attachments_needing_hash_backfill({"2025-12": pd}, attachment_ids=["a2"]), ["a2"])


class LoaderSqlHelpersTest(unittest.TestCase):
    def test_sql_str_escapes(self):
        self.assertEqual(_sql_str("a'b"), "'a''b'")

    def test_in_clause(self):
        self.assertEqual(_in_clause(["a", "b"]), "('a','b')")

    def test_in_clause_empty_is_none(self):
        self.assertIsNone(_in_clause([]))


if __name__ == "__main__":
    unittest.main()
