"""Tests for the attachment_not_downloaded alert (IMP-004 / issue #41).

The analysis pass raises one ``attachment_not_downloaded`` (``warning``) alert per attachment whose
mirror row has no stored page linkage (falsy ``file_path``). Covers (per the spec's user stories):

- US2 — one alert per missing attachment (FR-006), deterministic idempotent id (FR-007), no alert
  when pages are present (self-clearing), empty-string file_path treated as missing, and the
  deep-link metadata (FR-006).

Run: ``python -m unittest discover -s scripts/tests -t scripts``
"""

import unittest

from common import det_id

from analysis.checks.attachments import check_attachment_not_downloaded
from analysis.models import PeriodData


def _period(attachments):
    return PeriodData(
        period="2025-12",
        raw={},
        report={},
        entries=[],
        category_subtotals=[],
        attachments=attachments,
    )


def _att(aid, entry_id, *, file_path=None, external_document_id=42):
    return {
        "id": aid,
        "entry_id": entry_id,
        "file_path": file_path,
        "external_document_id": external_document_id,
    }


class CheckAttachmentNotDownloadedTest(unittest.TestCase):
    def test_one_alert_per_missing_attachment(self):
        p = _period([_att("a1", "e1"), _att("a2", "e2")])
        alerts = check_attachment_not_downloaded(p)
        self.assertEqual(len(alerts), 2)
        self.assertTrue(all(a.type == "attachment_not_downloaded" for a in alerts))
        self.assertTrue(all(a.severity == "warning" for a in alerts))
        self.assertTrue(all(a.reference_period == "2025-12" for a in alerts))

    def test_no_alert_when_pages_present(self):
        p = _period([_att("a1", "e1", file_path="2025-12/e1_p1.png")])
        self.assertEqual(check_attachment_not_downloaded(p), [])

    def test_mixed(self):
        p = _period(
            [
                _att("a1", "e1", file_path="2025-12/e1_p1.png"),  # has pages → no alert
                _att("a2", "e2"),  # missing → alert
            ]
        )
        alerts = check_attachment_not_downloaded(p)
        self.assertEqual(len(alerts), 1)
        self.assertEqual(alerts[0].metadata["attachment_id"], "a2")

    def test_empty_string_file_path_is_missing(self):
        p = _period([_att("a1", "e1", file_path="")])
        alerts = check_attachment_not_downloaded(p)
        self.assertEqual(len(alerts), 1)

    def test_deterministic_idempotent_id(self):
        p = _period([_att("a1", "e1")])
        first = check_attachment_not_downloaded(p)[0]
        second = check_attachment_not_downloaded(p)[0]
        expected = det_id("alert", "2025-12", "attachment_not_downloaded", "a1")
        self.assertEqual(first.id, expected)
        self.assertEqual(first.id, second.id)

    def test_metadata_for_deep_link(self):
        p = _period([_att("a1", "e1", external_document_id=99)])
        meta = check_attachment_not_downloaded(p)[0].metadata
        self.assertEqual(meta["attachment_id"], "a1")
        self.assertEqual(meta["entry_id"], "e1")
        self.assertEqual(meta["external_document_id"], 99)


if __name__ == "__main__":
    unittest.main()
