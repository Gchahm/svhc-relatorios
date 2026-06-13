"""US2: ``mark-pending`` clears the classified stamp + invalidates staging, atomically, on real D1."""

from __future__ import annotations

import unittest

from analysis.extractions import mark_pending
from common import det_id

from . import _harness as h


class TestMarkPending(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        h.seed_once()  # full first-time provision (migrations + base data)
        cls.ids = h.ids()

    def setUp(self):
        h.restore()
        self.e3_att = self.ids["attachments"]["E3"]
        self.e4_att = self.ids["attachments"]["E4"]

    def test_clears_classified_stamp(self):
        # E3 starts classified (non-NULL stamp).
        self.assertIsNotNone(
            h.scalar(f"SELECT classified_at FROM attachment_state WHERE attachment_id = '{self.e3_att}'")
        )
        n = mark_pending("local", attachment_ids=[self.e3_att])
        self.assertEqual(n, 1)
        # Now NULL (pending), the row still exists.
        self.assertEqual(h.count("attachment_state", f"attachment_id = '{self.e3_att}'"), 1)
        self.assertIsNone(
            h.scalar(f"SELECT classified_at FROM attachment_state WHERE attachment_id = '{self.e3_att}'")
        )

    def test_invalidates_staging(self):
        # E4 owns a staging row; mark-pending on E4 drops it in the same batch.
        self.assertEqual(h.count("page_classifications", f"attachment_id = '{self.e4_att}'"), 1)
        mark_pending("local", attachment_ids=[self.e4_att])
        self.assertEqual(h.count("page_classifications", f"attachment_id = '{self.e4_att}'"), 0)

    def test_idempotent(self):
        mark_pending("local", attachment_ids=[self.e3_att])
        mark_pending("local", attachment_ids=[self.e3_att])
        self.assertIsNone(
            h.scalar(f"SELECT classified_at FROM attachment_state WHERE attachment_id = '{self.e3_att}'")
        )

    def test_entry_id_scope(self):
        # Entry-id scope resolves to the attachment via the read-only attachments subquery.
        e3_entry = self.ids["entries"]["E3"]
        mark_pending("local", entry_ids=[e3_entry])
        self.assertIsNone(
            h.scalar(f"SELECT classified_at FROM attachment_state WHERE attachment_id = '{self.e3_att}'")
        )


if __name__ == "__main__":
    unittest.main()
