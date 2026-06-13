"""Tests for analysis.mismatches.detect_attachment_mismatches (TEST-002 / issue #69).

The single source of truth shared by the alert check and the `mismatches` CLI. Pure read of
the persisted `attachment_analyses` match flags — no D1.
"""

import unittest

from analysis.mismatches import (
    KIND_AMOUNT,
    KIND_DATE,
    KIND_PAGE_ERROR,
    KIND_VENDOR,
    detect_attachment_mismatches,
)

from tests._fixtures import analysis_row, attachment, entry, make_period, make_refs


class DetectAttachmentMismatchesTest(unittest.TestCase):
    def _period(self, analyses, *, entries=None, attachments=None):
        return make_period(
            "2025-12",
            entries=entries or [],
            attachments=attachments or [],
            raw_extra={"attachment_analyses": analyses},
        )

    def test_no_analyses_yields_nothing(self):
        pd = self._period([])
        self.assertEqual(detect_attachment_mismatches(pd, make_refs()), [])

    def test_all_flags_pass_yields_nothing(self):
        e = entry("e1", amount=100.0, vendor_id="v1")
        a = attachment("a1", "e1")
        pd = self._period(
            [analysis_row("a1", amount_match=1, vendor_match=1, date_match=1)],
            entries=[e],
            attachments=[a],
        )
        self.assertEqual(detect_attachment_mismatches(pd, make_refs()), [])

    def test_one_mismatch_per_failing_flag(self):
        e = entry("e1", amount=100.0, vendor_id="v1")
        a = attachment("a1", "e1")
        refs = make_refs(vendors=[{"id": "v1", "name": "ACME LTDA"}])
        pd = self._period(
            [
                analysis_row(
                    "a1",
                    amount_match=0,
                    vendor_match=0,
                    date_match=0,
                    extracted_amount=200.0,
                    issuer_name="OTHER CO",
                    extracted_date="01/06/2024",
                )
            ],
            entries=[e],
            attachments=[a],
        )
        out = detect_attachment_mismatches(pd, refs)
        kinds = sorted(m.kind for m in out)
        self.assertEqual(kinds, sorted([KIND_AMOUNT, KIND_VENDOR, KIND_DATE]))

        by_kind = {m.kind: m for m in out}
        self.assertEqual(by_kind[KIND_AMOUNT].ledger_value, 100.0)
        self.assertEqual(by_kind[KIND_AMOUNT].extracted_value, 200.0)
        self.assertEqual(by_kind[KIND_VENDOR].ledger_value, "ACME LTDA")
        self.assertEqual(by_kind[KIND_VENDOR].extracted_value, "OTHER CO")
        self.assertEqual(by_kind[KIND_DATE].ledger_value, "2025-12")
        self.assertEqual(by_kind[KIND_DATE].extracted_value, "01/06/2024")
        self.assertTrue(all(m.entry_id == "e1" and m.attachment_id == "a1" for m in out))

    def test_page_error_short_circuits_field_checks(self):
        e = entry("e1", amount=100.0, vendor_id="v1")
        a = attachment("a1", "e1")
        pd = self._period(
            [analysis_row("a1", error="image unreadable", amount_match=0, vendor_match=0)],
            entries=[e],
            attachments=[a],
        )
        out = detect_attachment_mismatches(pd, make_refs())
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0].kind, KIND_PAGE_ERROR)
        self.assertEqual(out[0].detail, "image unreadable")

    def test_missing_attachment_or_entry_gives_none_entry_id(self):
        # analysis references an attachment not present in the period.
        pd = self._period([analysis_row("ghost", amount_match=0, extracted_amount=5.0)])
        out = detect_attachment_mismatches(pd, make_refs())
        self.assertEqual(len(out), 1)
        self.assertIsNone(out[0].entry_id)
        self.assertIsNone(out[0].ledger_value)  # no entry → no ledger amount

    def test_vendor_mismatch_with_no_vendor_id_uses_none(self):
        e = entry("e1", amount=100.0)  # no vendor_id
        a = attachment("a1", "e1")
        pd = self._period(
            [analysis_row("a1", vendor_match=0, issuer_name="X")],
            entries=[e],
            attachments=[a],
        )
        out = detect_attachment_mismatches(pd, make_refs())
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0].kind, KIND_VENDOR)
        self.assertIsNone(out[0].ledger_value)

    def test_none_flag_is_not_a_mismatch(self):
        # amount_match None (unknown) must NOT fire — only an explicit 0 does.
        e = entry("e1", amount=100.0)
        a = attachment("a1", "e1")
        pd = self._period(
            [analysis_row("a1", amount_match=None, vendor_match=None, date_match=None)],
            entries=[e],
            attachments=[a],
        )
        self.assertEqual(detect_attachment_mismatches(pd, make_refs()), [])


if __name__ == "__main__":
    unittest.main()
