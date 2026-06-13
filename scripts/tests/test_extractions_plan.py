"""Tests for analysis.extractions pure plan/page-ref/mark-pending logic (TEST-002 / issue #69).

`build_plan` is a pure function of the loaded periods + refs (and the page-image tokens). The
D1-writing paths (apply, the SQL-emitting branch of mark_pending) are left to TEST-004.
"""

import unittest

from analysis.extractions import _page_refs_for_doc, build_plan, mark_pending

from tests._fixtures import attachment, entry, make_period, make_refs


class BuildPlanTest(unittest.TestCase):
    def test_one_envelope_per_period_with_group_and_members(self):
        e1 = entry("e1", amount=60.0, vendor_id="v1")
        e2 = entry("e2", amount=40.0, vendor_id="v1")
        a1 = attachment("a1", "e1", file_path="2025-12/a1_p1.png", content_hash="H")
        a2 = attachment("a2", "e2", file_path="2025-12/a2_p1.png", content_hash="H")
        pd = make_period("2025-12", entries=[e1, e2], attachments=[a1, a2])
        refs = make_refs(vendors=[{"id": "v1", "name": "ACME"}])
        envelopes = build_plan({"2025-12": pd}, refs)
        self.assertEqual(len(envelopes), 1)
        env = envelopes[0]
        self.assertEqual(env["period"], "2025-12")
        self.assertEqual(len(env["groups"]), 1)
        group = env["groups"][0]
        # representative is the highest-amount item (a1 / 60)
        self.assertEqual(group["representative_attachment_id"], "a1")
        self.assertEqual(group["group_size"], 2)
        self.assertEqual(group["sibling_sum"], 100.0)
        self.assertEqual(len(group["members"]), 2)
        rep_member = next(m for m in group["members"] if m["is_representative"])
        self.assertEqual(rep_member["attachment_id"], "a1")
        self.assertEqual(rep_member["vendor_name"], "ACME")
        # one page on the representative
        self.assertEqual(len(group["pages"]), 1)
        self.assertEqual(group["pages"][0]["page_label"], "p1")

    def test_recorded_flag_from_page_classifications(self):
        e1 = entry("e1", amount=60.0)
        a1 = attachment("a1", "e1", file_path="2025-12/a1_p1.png", content_hash="H")
        pd = make_period(
            "2025-12",
            entries=[e1],
            attachments=[a1],
            raw_extra={"page_classifications": [{"attachment_id": "a1", "page_label": "p1"}]},
        )
        envelopes = build_plan({"2025-12": pd}, make_refs())
        page = envelopes[0]["groups"][0]["pages"][0]
        self.assertTrue(page["recorded"])

    def test_classified_attachment_excluded(self):
        e1 = entry("e1", amount=60.0)
        a1 = attachment("a1", "e1", content_hash="H", classified_at=123)
        pd = make_period("2025-12", entries=[e1], attachments=[a1])
        self.assertEqual(build_plan({"2025-12": pd}, make_refs()), [])


class PageRefsTest(unittest.TestCase):
    def test_tokens_to_page_refs(self):
        doc = {"id": "a1", "file_path": "2025-12/a1_p1.png;2025-12/a1_p2.png"}
        refs = _page_refs_for_doc(doc)
        self.assertEqual([r["page_label"] for r in refs], ["p1", "p2"])
        self.assertTrue(all(r["attachment_id"] == "a1" for r in refs))
        self.assertTrue(all(r["read_path"].endswith(".png") for r in refs))

    def test_none_doc(self):
        self.assertEqual(_page_refs_for_doc(None), [])


class MarkPendingNoIdsTest(unittest.TestCase):
    def test_no_ids_returns_zero_without_db(self):
        # With no attachment/entry ids the function returns 0 and never reaches execute_sql.
        self.assertEqual(mark_pending("local", "2025-12"), 0)


if __name__ == "__main__":
    unittest.main()
