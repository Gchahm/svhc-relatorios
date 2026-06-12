"""Tests for page_classifications staging-row pruning (feature 035 / issue #42).

Covers the pure SQL helper and the two cleanup hooks:
  - ``apply-extractions`` (``attachments._merge_and_write``) deletes an attachment's staging rows
    in the SAME atomic batch as its authoritative ``attachment_analyses`` insert;
  - ``mark-pending`` (``extractions.mark_pending``) deletes a re-queued attachment's staging rows
    in the same batch that clears ``attachment_state.classified_at`` (and stays a no-op with no ids).

Run: ``python -m unittest discover -s scripts/tests -t scripts``
"""

import unittest

from analysis import attachments, extractions
from analysis.attachments import AttachmentAnalysisResult, _merge_and_write
from analysis.extractions import mark_pending
from analysis.page_classifications import _prune_page_classifications_sql


class PruneSqlHelperTest(unittest.TestCase):
    def test_empty_list_is_empty_string(self):
        self.assertEqual(_prune_page_classifications_sql([]), "")

    def test_all_falsy_ids_is_empty_string(self):
        # Falsy ids (None / "") are filtered; an all-falsy list yields no DELETE.
        self.assertEqual(_prune_page_classifications_sql([None, ""]), "")

    def test_single_id(self):
        self.assertEqual(
            _prune_page_classifications_sql(["att-1"]),
            "DELETE FROM page_classifications WHERE attachment_id IN ('att-1');",
        )

    def test_multiple_ids_comma_joined_no_spaces(self):
        self.assertEqual(
            _prune_page_classifications_sql(["a", "b"]),
            "DELETE FROM page_classifications WHERE attachment_id IN ('a','b');",
        )

    def test_single_quote_is_escaped(self):
        self.assertEqual(
            _prune_page_classifications_sql(["o'brien"]),
            "DELETE FROM page_classifications WHERE attachment_id IN ('o''brien');",
        )

    def test_ends_with_semicolon(self):
        self.assertTrue(_prune_page_classifications_sql(["x"]).endswith(";"))


class ApplyConsumesStagingTest(unittest.TestCase):
    """US1 — apply consumes an attachment's staging rows atomically with the analysis insert."""

    def _result(self):
        return AttachmentAnalysisResult(
            attachment_id="att-1",
            entry_id="ent-1",
            entry_amount=100.0,
            extracted_amount=100.0,
            amount_match=True,
        )

    def _capture_merge_sql(self):
        captured = []
        orig = attachments.d1.execute_sql
        attachments.d1.execute_sql = lambda sql, *, target: captured.append(sql)
        try:
            _merge_and_write(self._result(), target="local")
        finally:
            attachments.d1.execute_sql = orig
        return captured

    def test_staging_delete_in_same_single_batch_as_insert(self):
        captured = self._capture_merge_sql()
        # Exactly one batch — the staging delete adds no separate round trip (atomicity, FR-002).
        self.assertEqual(len(captured), 1)
        sql = captured[0]
        self.assertIn('INSERT OR REPLACE INTO "attachment_analyses"', sql)
        self.assertIn("DELETE FROM page_classifications WHERE attachment_id IN ('att-1');", sql)

    def test_staging_delete_scoped_to_attachment_and_follows_insert(self):
        sql = self._capture_merge_sql()[0]
        # FR-006: scoped strictly to this attachment's id.
        self.assertIn("WHERE attachment_id IN ('att-1')", sql)
        # The consume happens AFTER the analysis insert lands.
        self.assertLess(
            sql.index('INSERT OR REPLACE INTO "attachment_analyses"'),
            sql.index("DELETE FROM page_classifications"),
        )

    def test_failed_write_does_not_commit_staging_delete_separately(self):
        calls = []

        def boom(sql, *, target):
            calls.append(sql)
            raise RuntimeError("simulated D1 failure")

        orig = attachments.d1.execute_sql
        attachments.d1.execute_sql = boom
        try:
            with self.assertRaises(RuntimeError):
                _merge_and_write(self._result(), target="local")
        finally:
            attachments.d1.execute_sql = orig
        # Only the single combined batch was attempted — no standalone staging DELETE could have
        # committed without the insert, so the staging rows survive a failed write (SC-003).
        self.assertEqual(len(calls), 1)
        self.assertIn("DELETE FROM page_classifications", calls[0])


class MarkPendingClearsStagingTest(unittest.TestCase):
    """US2 — mark-pending clears a re-queued attachment's staging rows in one batch."""

    def _capture(self, **kwargs):
        captured = []
        orig = extractions.d1.execute_sql
        extractions.d1.execute_sql = lambda sql, *, target: captured.append(sql)
        try:
            n = mark_pending("local", **kwargs)
        finally:
            extractions.d1.execute_sql = orig
        return captured, n

    def test_attachment_scope_clears_state_and_staging_in_one_batch(self):
        captured, n = self._capture(attachment_ids=["att-1"])
        self.assertEqual(len(captured), 1)
        sql = captured[0]
        self.assertIn("UPDATE attachment_state SET classified_at = NULL", sql)
        self.assertIn("DELETE FROM page_classifications WHERE attachment_id IN ('att-1')", sql)
        self.assertEqual(n, 1)

    def test_entry_scope_uses_readonly_attachments_subquery(self):
        captured, _ = self._capture(entry_ids=["ent-9"])
        sql = captured[0]
        # The staging DELETE reuses the same read-only subquery the UPDATE uses (no mirror write).
        self.assertIn(
            "DELETE FROM page_classifications WHERE attachment_id IN "
            "(SELECT id FROM attachments WHERE entry_id IN ('ent-9'))",
            sql,
        )
        # FR-005: no write to the mirror `attachments` table.
        self.assertNotIn("UPDATE attachments", sql)
        self.assertNotIn("INSERT INTO attachments", sql)

    def test_no_ids_is_noop_returns_zero(self):
        captured, n = self._capture()
        self.assertEqual(captured, [])  # FR-004: execute_sql never called.
        self.assertEqual(n, 0)


if __name__ == "__main__":
    unittest.main()
