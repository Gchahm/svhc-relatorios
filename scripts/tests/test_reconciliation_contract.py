"""Cross-language reconciliation contract test — Python side (IMP-006 / issue #43).

The over/within/under reconciliation decision lives in two implementations, two languages:
``analysis.nf_groups.reconcile_group`` (Python — drives ``amount_match``, shared-NF
reconciliation, and the ``document_overpayment`` alert) and ``documentStatus`` in
``src/lib/documents.ts`` (TypeScript — drives the over/within/under badge on
``/dashboard/documents``). They were identical but nothing bound them, so the first
unilateral tweak would make the badge and the alert that created it silently disagree.

This test pins the Python side to the **single shared fixture**
``scripts/analysis/reconciliation_contract.json``; ``src/lib/documents.test.mjs`` pins the
TS side to the same file. A unilateral change to either side's tolerance constants or
comparison operators flips a fixture case and fails that side's test.

The fixture uses the TS-flavored canonical status vocabulary
(``within``/``over``/``under``/``unknown``); this test maps ``reconcile_group``'s output
through the documented equivalence below.

Run: ``python -m unittest discover -s scripts/tests -t scripts``
"""

import json
import unittest
from pathlib import Path

from analysis import nf_groups

# Canonical fixture — the single source of truth shared with the TS test.
FIXTURE = Path(__file__).resolve().parent.parent / "analysis" / "reconciliation_contract.json"

# Python reconcile_group names -> canonical (TS-flavored) names in the fixture.
TO_CANONICAL = {
    "reconciled": "within",
    "over_claim": "over",
    "under_claim": "under",
    None: "unknown",
}


class ReconciliationContractTest(unittest.TestCase):
    def setUp(self):
        self.data = json.loads(FIXTURE.read_text())
        self.cases = self.data["cases"]

    def test_fixture_is_well_formed(self):
        """Every case has the required shape and a valid canonical status (FR-001)."""
        self.assertTrue(self.cases, "fixture must contain at least one case")
        valid = {"within", "over", "under", "unknown"}
        names = set()
        for c in self.cases:
            self.assertIn("name", c)
            self.assertIn("sum", c)
            self.assertIn("total", c)  # may be null
            self.assertIn(c["status"], valid, f"{c['name']}: invalid status {c['status']!r}")
            self.assertNotIn(c["name"], names, f"duplicate case name {c['name']!r}")
            names.add(c["name"])

    def test_fixture_covers_required_boundaries(self):
        """The required minimum boundary cases are present (FR-002)."""
        names = {c["name"] for c in self.cases}
        required = {
            "exact_match",
            "abs_band_inclusive",
            "abs_only_small_total",
            "abs_only_small_total_under",
            "rel_band_inside",
            "rel_band_exact_excluded",
            "clear_over",
            "clear_under",
            "null_total",
            "zero_total",
            "negative_total",
        }
        self.assertTrue(required <= names, f"missing required cases: {required - names}")

    def test_reconcile_group_matches_contract(self):
        """reconcile_group, mapped to canonical names, equals the fixture (FR-003/FR-005)."""
        for c in self.cases:
            with self.subTest(case=c["name"]):
                raw = nf_groups.reconcile_group(c["sum"], c["total"])
                self.assertIn(raw, TO_CANONICAL, f"unexpected reconcile_group output {raw!r}")
                self.assertEqual(
                    TO_CANONICAL[raw],
                    c["status"],
                    f"{c['name']}: sum={c['sum']} total={c['total']} -> "
                    f"reconcile_group={raw!r} (canonical {TO_CANONICAL[raw]!r}) "
                    f"but fixture expects {c['status']!r}",
                )


if __name__ == "__main__":
    unittest.main()
