"""US1: the synthetic seed provisions the expected local D1 + R2 state, idempotently."""

from __future__ import annotations

import unittest

from e2e import synthetic

from . import _harness as h


class TestSeed(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.summary = h.seed_once()
        cls.ids = h.ids()

    def test_report_and_entries(self):
        rid = self.ids["report_id"]
        self.assertEqual(h.count("accountability_reports", f"period = '{synthetic.PERIOD}'"), 1)
        self.assertEqual(h.count("entries", f"report_id = '{rid}'"), 6)

    def test_attachments_and_state_split(self):
        rid = self.ids["report_id"]
        # 5 attachments (one per E1..E5).
        n_att = h.count(
            "attachments",
            f"entry_id IN (SELECT id FROM entries WHERE report_id = '{rid}')",
        )
        self.assertEqual(n_att, 5)
        # E4 is PENDING: no attachment_state row OR NULL classified_at.
        e4_att = self.ids["attachments"]["E4"]
        pending = h.scalar(
            "SELECT classified_at FROM attachment_state WHERE attachment_id = "
            f"'{e4_att}'"
        )
        self.assertIsNone(pending)  # no row → NULL scalar
        # E1/E2/E3/E5 are classified.
        for key in ("E1", "E2", "E3", "E5"):
            att = self.ids["attachments"][key]
            stamped = h.scalar(f"SELECT classified_at FROM attachment_state WHERE attachment_id = '{att}'")
            self.assertIsNotNone(stamped, f"{key} should be classified")

    def test_analyses_and_records(self):
        att_ids = ",".join(f"'{self.ids['attachments'][k]}'" for k in ("E1", "E2", "E3"))
        self.assertEqual(h.count("attachment_analyses", f"attachment_id IN ({att_ids})"), 3)
        an_ids = ",".join(f"'{self.ids['analyses'][k]}'" for k in ("E1", "E2", "E3"))
        self.assertEqual(h.count("attachment_analysis_records", f"attachment_analysis_id IN ({an_ids})"), 3)

    def test_documents_present(self):
        # build_documents derived the synthetic NF-1001 (over) + NF-1002 (within). The stored
        # document_number is the NORMALIZED form (separators stripped, uppercased): "NF1001".
        self.assertGreaterEqual(h.count("documents", "document_number = 'NF1001'"), 1)
        self.assertGreaterEqual(h.count("documents", "document_number = 'NF1002'"), 1)

    def test_deep_link_alerts(self):
        self.assertEqual(
            h.count(
                "alerts",
                f"type = 'attachment_amount_mismatch' AND reference_period = '{synthetic.PERIOD}'",
            ),
            1,
        )
        # The overpayment alert carries entry_ids in metadata.
        meta = h.scalar(
            "SELECT metadata FROM alerts WHERE type = 'document_overpayment' "
            f"AND reference_period = '{synthetic.PERIOD}'"
        )
        self.assertIsNotNone(meta)
        self.assertIn("entry_ids", meta)

    def test_r2_images_present(self):
        for key in self.ids["attachments"]:
            eid = self.ids["entries"][key]
            self.assertTrue(h.r2_exists(synthetic.file_path_for(eid)), f"missing R2 image for {key}")

    def test_idempotent_reseed(self):
        rid = self.ids["report_id"]
        before = h.count("entries", f"report_id = '{rid}'")
        h.seed_once()  # re-run
        after = h.count("entries", f"report_id = '{rid}'")
        self.assertEqual(before, after)
        self.assertEqual(after, 6)


if __name__ == "__main__":
    unittest.main()
