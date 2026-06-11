"""Tests for the atomic attachment-analysis writeback (feature 024 / issue #37).

Asserts ``attachments._merge_and_write`` submits ONE batch containing the two DELETEs, the analysis
INSERT, and the ``attachment_state`` classified-stamp upsert — and that a simulated failure
propagates without ever committing the stamp/delete in a separate batch (so the attachment stays
pending and self-heals). The stamp moved off the mirror table ``attachments`` into the
analysis-owned ``attachment_state`` table (BUG-002 / issue #33).

Run: ``python -m unittest discover -s scripts/tests -t scripts``
"""

import unittest

from analysis import attachments
from analysis.attachments import AttachmentAnalysisResult, _merge_and_write


class _Boom(Exception):
    pass


class AttachmentWritebackAtomicTest(unittest.TestCase):
    def _result(self):
        return AttachmentAnalysisResult(
            attachment_id="att-1",
            entry_id="ent-1",
            entry_amount=100.0,
            extracted_amount=100.0,
            amount_match=True,
        )

    def test_single_batch_with_deletes_insert_and_stamp(self):
        captured = []

        def fake_execute(sql, *, target):
            captured.append(sql)

        orig = attachments.d1.execute_sql
        attachments.d1.execute_sql = fake_execute
        try:
            _merge_and_write(self._result(), target="local")
        finally:
            attachments.d1.execute_sql = orig

        # Exactly one batch (no separate upsert_tables call).
        self.assertEqual(len(captured), 1)
        sql = captured[0]
        self.assertIn("DELETE FROM attachment_analysis_records WHERE attachment_analysis_id =", sql)
        self.assertIn("DELETE FROM attachment_analyses WHERE attachment_id =", sql)
        self.assertIn('INSERT OR REPLACE INTO "attachment_analyses"', sql)
        self.assertIn("INSERT INTO attachment_state (attachment_id, classified_at)", sql)
        # The mirror table is never written by the pipeline (issue #33).
        self.assertNotIn("UPDATE attachments SET", sql)

    def test_stamp_is_in_same_batch_as_insert(self):
        captured = []
        attachments_d1 = attachments.d1
        orig = attachments_d1.execute_sql
        attachments_d1.execute_sql = lambda sql, *, target: captured.append(sql)
        try:
            _merge_and_write(self._result(), target="local")
        finally:
            attachments_d1.execute_sql = orig

        sql = captured[0]
        # The classified_at stamp MUST NOT appear in any batch that lacks the analysis insert.
        self.assertIn("INSERT INTO attachment_state (attachment_id, classified_at)", sql)
        self.assertIn('INSERT OR REPLACE INTO "attachment_analyses"', sql)
        # Order within the batch: insert precedes the stamp.
        self.assertLess(
            sql.index('INSERT OR REPLACE INTO "attachment_analyses"'),
            sql.index("INSERT INTO attachment_state (attachment_id, classified_at)"),
        )

    def test_failure_propagates_with_no_separate_committed_delete(self):
        calls = []

        def boom(sql, *, target):
            calls.append(sql)
            raise _Boom("simulated wrangler/D1 failure")

        orig = attachments.d1.execute_sql
        attachments.d1.execute_sql = boom
        try:
            with self.assertRaises(_Boom):
                _merge_and_write(self._result(), target="local")
        finally:
            attachments.d1.execute_sql = orig

        # Only the single combined batch was attempted — there is no standalone DELETE/stamp call
        # that could have committed without the insert. The attachment therefore stays pending.
        self.assertEqual(len(calls), 1)
        self.assertIn("DELETE FROM attachment_analyses", calls[0])
        self.assertIn('INSERT OR REPLACE INTO "attachment_analyses"', calls[0])


if __name__ == "__main__":
    unittest.main()
