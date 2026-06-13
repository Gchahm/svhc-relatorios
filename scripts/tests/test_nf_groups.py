"""Tests for analysis.nf_groups tolerance math + grouping (TEST-002 / issue #69).

`within_tolerance` / `reconcile_group` are the shared shared-NF reconciliation, mirrored in
TypeScript (documents.ts) and bound by the contract fixture. `group_attachments` groups by
the persisted content_hash. All pure.
"""

import unittest

from analysis.nf_groups import (
    AMOUNT_ABS_TOL,
    AMOUNT_REL_TOL,
    group_attachments,
    reconcile_group,
    within_tolerance,
)


class WithinToleranceTest(unittest.TestCase):
    def test_exact_match(self):
        self.assertTrue(within_tolerance(100.0, 100.0))

    def test_within_absolute_band(self):
        self.assertTrue(within_tolerance(100.04, 100.0))  # diff 0.04 <= 0.05
        self.assertTrue(within_tolerance(100.05, 100.0))  # diff exactly 0.05

    def test_just_outside_absolute_but_within_relative(self):
        # diff 4.0 on 1000 = 0.4% < 5% rel → within
        self.assertTrue(within_tolerance(1004.0, 1000.0))

    def test_outside_both_bands(self):
        # diff 0.06 abs (> 0.05) and 6% rel (> 5%) on 1.0
        self.assertFalse(within_tolerance(1.06, 1.0))

    def test_relative_band_boundary_is_strict(self):
        # diff exactly 5% must NOT pass (strict <), and abs 5.0 > 0.05
        self.assertFalse(within_tolerance(105.0, 100.0))
        # just under 5%
        self.assertTrue(within_tolerance(104.99, 100.0))

    def test_zero_reference_uses_only_absolute(self):
        self.assertTrue(within_tolerance(0.03, 0.0))
        self.assertFalse(within_tolerance(0.10, 0.0))

    def test_constants(self):
        self.assertEqual(AMOUNT_ABS_TOL, 0.05)
        self.assertEqual(AMOUNT_REL_TOL, 0.05)


class ReconcileGroupTest(unittest.TestCase):
    def test_none_total(self):
        self.assertIsNone(reconcile_group(100.0, None))

    def test_nonpositive_total(self):
        self.assertIsNone(reconcile_group(100.0, 0.0))
        self.assertIsNone(reconcile_group(100.0, -5.0))

    def test_reconciled(self):
        self.assertEqual(reconcile_group(100.0, 100.0), "reconciled")
        self.assertEqual(reconcile_group(100.04, 100.0), "reconciled")

    def test_over_claim(self):
        self.assertEqual(reconcile_group(150.0, 100.0), "over_claim")

    def test_under_claim(self):
        self.assertEqual(reconcile_group(50.0, 100.0), "under_claim")


class GroupAttachmentsTest(unittest.TestCase):
    def test_same_content_hash_merges(self):
        docs = [
            {"id": "a1", "content_hash": "H", "file_path": "p/a1.png"},
            {"id": "a2", "content_hash": "H", "file_path": "p/a2.png"},
            {"id": "a3", "content_hash": "K", "file_path": "p/a3.png"},
        ]
        groups = group_attachments(docs)
        self.assertEqual(sorted(groups.keys()), ["H", "K"])
        self.assertEqual({d["id"] for d in groups["H"]}, {"a1", "a2"})
        self.assertEqual({d["id"] for d in groups["K"]}, {"a3"})

    def test_missing_hash_falls_back_to_singleton_id_key(self):
        # No content_hash and a file_path that does not resolve to a hashable file →
        # singleton key derived from the id, never merged with another.
        docs = [
            {"id": "a1", "content_hash": None, "file_path": "/nonexistent/a1.png"},
            {"id": "a2", "content_hash": None, "file_path": "/nonexistent/a2.png"},
        ]
        groups = group_attachments(docs)
        self.assertIn("doc:a1", groups)
        self.assertIn("doc:a2", groups)
        self.assertEqual(len(groups), 2)


if __name__ == "__main__":
    unittest.main()
