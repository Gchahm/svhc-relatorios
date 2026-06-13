"""US2: ``_merge_and_write`` writes one attachment's roll-up atomically against real D1.

Exercises the feature-024/026/035 batch: clear old analysis rows + insert the roll-up + records,
stamp ``attachment_state.classified_at``, and prune the attachment's ``page_classifications``
staging rows — all in one ``execute_sql``. The seeded **E4** attachment is PENDING and owns a
staging row, so it is the natural subject.
"""

from __future__ import annotations

import unittest

from analysis.attachments import AttachmentAnalysisResult, PageAnalysisRecord, _merge_and_write
from common import det_id

from . import _harness as h


class TestMergeAndWrite(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        h.seed_once()
        cls.ids = h.ids()
        cls.e4_att = cls.ids["attachments"]["E4"]
        cls.e4_entry = cls.ids["entries"]["E4"]
        cls.an_id = det_id("attachment_analysis", cls.e4_att)

    def _result(self) -> AttachmentAnalysisResult:
        return AttachmentAnalysisResult(
            attachment_id=self.e4_att,
            entry_id=self.e4_entry,
            entry_amount=50.0,
            document_type="NF",
            extracted_amount=50.0,
            amount_match=True,
            extracted_cnpj="11222333000181",
            issuer_name="EXEMPLO Fornecedor B",
            vendor_match=True,
            extracted_date="12/01/2099",
            date_match=True,
            document_number="NF-9999",
            service_description="EXEMPLO servico pendente",
            records=[
                PageAnalysisRecord(
                    attachment_analysis_id=self.an_id,
                    analysis_type="page_extraction",
                    page_index=0,
                    page_label="p1",
                    artifact_role="invoice",
                    response={"numero": "NF-9999", "valor_total": 50.0},
                )
            ],
        )

    def setUp(self):
        # Cheap re-seed each test so prior runs/tests start from a clean (pending E4 + staging row)
        # state. restore() re-upserts the synthetic rows but skips migrations/build_documents/R2.
        h.restore()

    def test_writeback_inserts_stamps_and_prunes(self):
        # Precondition: E4 pending + has a staging row.
        self.assertEqual(h.count("page_classifications", f"attachment_id = '{self.e4_att}'"), 1)
        self.assertIsNone(
            h.scalar(f"SELECT classified_at FROM attachment_state WHERE attachment_id = '{self.e4_att}'")
        )

        _merge_and_write(self._result(), target="local")

        # Analysis roll-up + its record landed.
        self.assertEqual(h.count("attachment_analyses", f"attachment_id = '{self.e4_att}'"), 1)
        self.assertEqual(h.count("attachment_analysis_records", f"attachment_analysis_id = '{self.an_id}'"), 1)
        # Classified stamp written to attachment_state (non-NULL).
        stamp = h.scalar(f"SELECT classified_at FROM attachment_state WHERE attachment_id = '{self.e4_att}'")
        self.assertIsNotNone(stamp)
        # Staging consumed (feature 035): the E4 staging row is gone.
        self.assertEqual(h.count("page_classifications", f"attachment_id = '{self.e4_att}'"), 0)

    def test_idempotent(self):
        _merge_and_write(self._result(), target="local")
        _merge_and_write(self._result(), target="local")
        self.assertEqual(h.count("attachment_analyses", f"attachment_id = '{self.e4_att}'"), 1)
        self.assertEqual(h.count("attachment_analysis_records", f"attachment_analysis_id = '{self.an_id}'"), 1)


if __name__ == "__main__":
    unittest.main()
