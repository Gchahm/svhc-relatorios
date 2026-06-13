"""Feature 050 / issue #84: ``apply-extractions`` is staging-driven, against real D1.

Exercises the two acceptance behaviours over the feature-046 synthetic seed:

- **US1 (safety / INV-1)**: a PENDING attachment whose group representative has NO
  ``page_classifications`` staging rows is skipped — its existing ``attachment_analyses`` +
  records are left intact and it stays pending. (Previously such a bystander was overwritten with
  an all-empty roll-up.) Subject: E3 — seeded classified with a real analysis (NF-1002), owns no
  staging; we mark it pending so it is pending-without-staging.
- **US2 (scoping / INV-2)**: with staging recorded for exactly one attachment's representative
  (E4, the seeded pending-with-staging attachment), apply rolls up that group and stamps it, while
  the pending-without-staging bystander (E3) is untouched.

Note: every seeded attachment has a ``content_hash``, so ``apply_extractions`` performs no R2
materialization (it reads no image bytes for the roll-up) — the test needs no cache files.
"""

from __future__ import annotations

import unittest

from analysis.extractions import apply_extractions, mark_pending

from . import _harness as h


class TestApplyStagingDriven(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        h.seed_once()
        cls.ids = h.ids()
        cls.period = cls.ids["period"]
        cls.e3_att = cls.ids["attachments"]["E3"]
        cls.e3_an = cls.ids["analyses"]["E3"]
        cls.e4_att = cls.ids["attachments"]["E4"]

    def setUp(self):
        h.restore()

    def test_pending_without_staging_is_not_overwritten(self):
        # Make E3 pending-without-staging: it is seeded classified with an analysis (NF-1002) and
        # owns no staging row; mark-pending clears its stamp (and any staging — it has none).
        mark_pending("local", attachment_ids=[self.e3_att])
        self.assertIsNone(
            h.scalar(f"SELECT classified_at FROM attachment_state WHERE attachment_id = '{self.e3_att}'")
        )
        self.assertEqual(h.count("page_classifications", f"attachment_id = '{self.e3_att}'"), 0)
        # Precondition: E3's analysis + its record exist.
        self.assertEqual(h.count("attachment_analyses", f"attachment_id = '{self.e3_att}'"), 1)
        self.assertEqual(h.count("attachment_analysis_records", f"attachment_analysis_id = '{self.e3_an}'"), 1)
        before_number = h.scalar(f"SELECT document_number FROM attachment_analyses WHERE attachment_id = '{self.e3_att}'")
        self.assertEqual(before_number, "NF-1002")

        apply_extractions("local", [self.period])

        # E3 untouched: analysis row + record unchanged, document_number preserved, still pending.
        self.assertEqual(h.count("attachment_analyses", f"attachment_id = '{self.e3_att}'"), 1)
        self.assertEqual(h.count("attachment_analysis_records", f"attachment_analysis_id = '{self.e3_an}'"), 1)
        after_number = h.scalar(f"SELECT document_number FROM attachment_analyses WHERE attachment_id = '{self.e3_att}'")
        self.assertEqual(after_number, "NF-1002")
        self.assertIsNone(
            h.scalar(f"SELECT classified_at FROM attachment_state WHERE attachment_id = '{self.e3_att}'")
        )

    def test_targeted_reclassify_touches_only_staged_group(self):
        # E4 is pending and owns a staging row (seeded). E3 is pending-without-staging (mark it).
        mark_pending("local", attachment_ids=[self.e3_att])
        self.assertEqual(h.count("page_classifications", f"attachment_id = '{self.e4_att}'"), 1)
        # E4 has no analysis yet (it was never classified into a roll-up).
        self.assertEqual(h.count("attachment_analyses", f"attachment_id = '{self.e4_att}'"), 0)

        apply_extractions("local", [self.period])

        # E4's group was rolled up: analysis written, classified stamp set, staging pruned.
        self.assertEqual(h.count("attachment_analyses", f"attachment_id = '{self.e4_att}'"), 1)
        self.assertIsNotNone(
            h.scalar(f"SELECT classified_at FROM attachment_state WHERE attachment_id = '{self.e4_att}'")
        )
        self.assertEqual(h.count("page_classifications", f"attachment_id = '{self.e4_att}'"), 0)

        # E3 (pending-without-staging bystander) untouched: analysis still NF-1002, still pending.
        self.assertEqual(
            h.scalar(f"SELECT document_number FROM attachment_analyses WHERE attachment_id = '{self.e3_att}'"),
            "NF-1002",
        )
        self.assertIsNone(
            h.scalar(f"SELECT classified_at FROM attachment_state WHERE attachment_id = '{self.e3_att}'")
        )

    def test_no_staging_for_period_writes_nothing(self):
        # Clear the synthetic period's staging (E4), mark E3 + E4 pending -> no synthetic group is
        # staged. (Other periods' staging in shared local D1 is irrelevant — apply is scoped to
        # this period and selects only by this period's loaded staging rows.)
        mark_pending("local", attachment_ids=[self.e3_att, self.e4_att])
        self.assertEqual(h.count("page_classifications", f"attachment_id = '{self.e4_att}'"), 0)
        e3_before = h.scalar(f"SELECT document_number FROM attachment_analyses WHERE attachment_id = '{self.e3_att}'")

        apply_extractions("local", [self.period])

        # Nothing written: E4 still has no analysis, E3 unchanged, both still pending.
        self.assertEqual(h.count("attachment_analyses", f"attachment_id = '{self.e4_att}'"), 0)
        self.assertEqual(
            h.scalar(f"SELECT document_number FROM attachment_analyses WHERE attachment_id = '{self.e3_att}'"),
            e3_before,
        )


if __name__ == "__main__":
    unittest.main()
