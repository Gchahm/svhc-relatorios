"""Tests for analysis.checks.attachments alert generation (TEST-002 / issue #69).

Feature-018 per-attachment mismatch alerts + the IMP-004 not-downloaded alert. Detection is
delegated to analysis.mismatches (covered separately); here we assert the alert shaping.
"""

import unittest

from common import det_id

from analysis.checks.attachments import (
    check_attachment_mismatches,
    check_attachment_not_downloaded,
)

from tests._fixtures import analysis_row, attachment, entry, make_period, make_refs


class CheckAttachmentMismatchesTest(unittest.TestCase):
    def test_one_alert_per_kind_with_type_and_id(self):
        e = entry("e1", amount=100.0, vendor_id="v1")
        a = attachment("a1", "e1")
        refs = make_refs(vendors=[{"id": "v1", "name": "ACME"}])
        pd = make_period(
            "2025-12",
            entries=[e],
            attachments=[a],
            raw_extra={
                "attachment_analyses": [
                    analysis_row("a1", amount_match=0, vendor_match=0, extracted_amount=200.0, issuer_name="X")
                ]
            },
        )
        alerts = check_attachment_mismatches(pd, refs)
        types = sorted(al.type for al in alerts)
        self.assertEqual(types, ["attachment_amount_mismatch", "attachment_vendor_mismatch"])
        for al in alerts:
            self.assertEqual(al.severity, "warning")
            self.assertEqual(al.reference_period, "2025-12")
            self.assertEqual(al.metadata["attachment_id"], "a1")
            self.assertEqual(al.metadata["entry_id"], "e1")
            # deterministic, stable id keyed by attachment_id
            self.assertEqual(al.id, det_id("alert", "2025-12", al.type, "a1"))

    def test_page_error_is_info_with_detail(self):
        e = entry("e1", amount=100.0)
        a = attachment("a1", "e1")
        pd = make_period(
            "2025-12",
            entries=[e],
            attachments=[a],
            raw_extra={"attachment_analyses": [analysis_row("a1", error="ilegível")]},
        )
        alerts = check_attachment_mismatches(pd, make_refs())
        self.assertEqual(len(alerts), 1)
        self.assertEqual(alerts[0].type, "attachment_page_error")
        self.assertEqual(alerts[0].severity, "info")
        self.assertEqual(alerts[0].metadata["detail"], "ilegível")

    def test_no_mismatches_no_alerts(self):
        e = entry("e1", amount=100.0)
        a = attachment("a1", "e1")
        pd = make_period(
            "2025-12",
            entries=[e],
            attachments=[a],
            raw_extra={"attachment_analyses": [analysis_row("a1", amount_match=1, vendor_match=1, date_match=1)]},
        )
        self.assertEqual(check_attachment_mismatches(pd, make_refs()), [])


class CheckAttachmentNotDownloadedTest(unittest.TestCase):
    def test_alert_when_file_path_falsy(self):
        a = attachment("a1", "e1", file_path="", external_document_id="ext-9")
        pd = make_period("2025-12", attachments=[a])
        alerts = check_attachment_not_downloaded(pd)
        self.assertEqual(len(alerts), 1)
        al = alerts[0]
        self.assertEqual(al.type, "attachment_not_downloaded")
        self.assertEqual(al.severity, "warning")
        self.assertEqual(al.metadata["attachment_id"], "a1")
        self.assertEqual(al.metadata["entry_id"], "e1")
        self.assertEqual(al.metadata["external_document_id"], "ext-9")
        self.assertEqual(al.id, det_id("alert", "2025-12", "attachment_not_downloaded", "a1"))

    def test_no_alert_when_has_pages(self):
        a = attachment("a1", "e1", file_path="2025-12/x_p1.png")
        pd = make_period("2025-12", attachments=[a])
        self.assertEqual(check_attachment_not_downloaded(pd), [])


if __name__ == "__main__":
    unittest.main()
