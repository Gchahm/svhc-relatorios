"""Tests for scrape-time consistency validation (IMP-002 / issue #39).

The pure ``consistency`` module cross-checks a period's three independent views of the money —
per-``(subcategory, movement_type)`` entry sums vs the recorded category subtotals, and the
subtotal sums-by-movement-type vs the demonstrativo revenue/expense totals — and produces one
idempotent, period-scoped ``scrape_inconsistency`` ``warning`` alert (a single atomic SQL batch:
always a clearing DELETE, plus an INSERT only when inconsistent). Covers (per the spec's stories):

- US1 — detect + record: consistent period → no alert (lone DELETE); subcategory mismatch (dropped
  entry) → discrepancy + INSERT with affected entry ids; demonstrativo C/D mismatch → discrepancy;
  one-sided key → discrepancy; idempotent stable id; resolution graft (FR-001/003/005/008/009).
- US2 — operator surfacing: a one-line summary is produced for inconsistent periods (FR-006).
- US3 — no false alarms: sub-tolerance abs and relative differences → no discrepancy; C and D in the
  same subcategory never net against each other (FR-002, SC-002).

Run: ``python -m unittest discover -s scripts/tests -t scripts``
"""

import json
import unittest

from common import det_id
from scraper.consistency import (
    ALERT_SEVERITY,
    ALERT_TYPE,
    Discrepancy,
    build_consistency_writeback,
    detect_inconsistencies,
    within_tolerance,
)

PERIOD = "2026-01"


def _entry(eid, subcategory_id, amount, movement_type):
    return {"id": eid, "subcategory_id": subcategory_id, "amount": amount, "movement_type": movement_type}


def _subtotal(subcategory_id, amount, movement_type):
    return {"subcategory_id": subcategory_id, "amount": amount, "movement_type": movement_type}


class ToleranceTest(unittest.TestCase):
    def test_abs_floor(self):
        # Absolute floor: a 0.04 diff is tolerant regardless of the relative band.
        self.assertTrue(within_tolerance(100.04, 100.0))
        # A small diff against a tiny reference (abs floor only, relative band too small):
        self.assertFalse(within_tolerance(0.5, 0.1))  # diff 0.4 > 0.05; 0.4/0.1 = 4.0 not < 0.05

    def test_relative_band(self):
        # 6% off a large number → outside the relative band.
        self.assertFalse(within_tolerance(1060.0, 1000.0))
        # 4% off → inside.
        self.assertTrue(within_tolerance(1040.0, 1000.0))

    def test_zero_reference(self):
        # reference 0: only the abs floor applies.
        self.assertTrue(within_tolerance(0.04, 0.0))
        self.assertFalse(within_tolerance(5.0, 0.0))


class US1DetectTest(unittest.TestCase):
    """US1 — detect a ledger that does (not) add up."""

    def test_consistent_period_no_discrepancies(self):
        entries = [
            _entry("E1", "SUB1", 60.0, "D"),
            _entry("E2", "SUB1", 40.0, "D"),
            _entry("E3", "SUB2", 30.0, "C"),
        ]
        subtotals = [_subtotal("SUB1", 100.0, "D"), _subtotal("SUB2", 30.0, "C")]
        disc, affected = detect_inconsistencies(entries, subtotals, total_receitas=30.0, total_despesas=100.0)
        self.assertEqual(disc, [])
        self.assertEqual(affected, [])

    def test_subcategory_mismatch_dropped_entry(self):
        # The subtotal says 100 for SUB1/D but only one 60 entry survived (a dropped row).
        entries = [_entry("E1", "SUB1", 60.0, "D")]
        subtotals = [_subtotal("SUB1", 100.0, "D")]
        disc, affected = detect_inconsistencies(entries, subtotals, total_receitas=0.0, total_despesas=100.0)
        sub_disc = [d for d in disc if d.level == "subcategory"]
        self.assertEqual(len(sub_disc), 1)
        self.assertEqual(sub_disc[0].subcategory_id, "SUB1")
        self.assertEqual(sub_disc[0].movement_type, "D")
        self.assertEqual(sub_disc[0].computed_sum, 60.0)
        self.assertEqual(sub_disc[0].reported_total, 100.0)
        self.assertIn("E1", affected)

    def test_one_sided_key_entries_without_subtotal(self):
        # An entry exists for a key with NO subtotal → reported 0 → discrepancy.
        entries = [_entry("E1", "SUB9", 25.0, "D")]
        subtotals = []
        disc, affected = detect_inconsistencies(entries, subtotals, total_receitas=0.0, total_despesas=25.0)
        sub_disc = [d for d in disc if d.level == "subcategory"]
        self.assertEqual(len(sub_disc), 1)
        self.assertEqual(sub_disc[0].reported_total, 0.0)
        self.assertEqual(sub_disc[0].computed_sum, 25.0)

    def test_demonstrativo_mismatch(self):
        # Subcategory checks pass, but the demonstrativo totals disagree with the subtotal sums.
        entries = [_entry("E1", "SUB1", 100.0, "D"), _entry("E2", "SUB2", 50.0, "C")]
        subtotals = [_subtotal("SUB1", 100.0, "D"), _subtotal("SUB2", 50.0, "C")]
        # Reported demonstrativo wrong: despesas 999 (vs 100), receitas 999 (vs 50).
        disc, affected = detect_inconsistencies(entries, subtotals, total_receitas=999.0, total_despesas=999.0)
        dem = [d for d in disc if d.level == "demonstrativo"]
        self.assertEqual({d.movement_type for d in dem}, {"C", "D"})
        # No subcategory-level failure → no affected entry ids.
        self.assertEqual(affected, [])


class US3NoFalseAlarmTest(unittest.TestCase):
    """US3 — sub-tolerance rounding never fires; C/D never net within a subcategory."""

    def test_sub_tolerance_rounding(self):
        entries = [_entry("E1", "SUB1", 100.02, "D")]
        subtotals = [_subtotal("SUB1", 100.0, "D")]
        disc, _ = detect_inconsistencies(entries, subtotals, total_receitas=0.0, total_despesas=100.0)
        self.assertEqual(disc, [])

    def test_credit_debit_same_subcategory_not_netted(self):
        # SUB1 has a 100 D entry and a 100 C entry; subtotals carry them separately. If they were
        # netted, the sum would be 0 and the per-key subtotals (each 100) would both look wrong.
        entries = [_entry("E1", "SUB1", 100.0, "D"), _entry("E2", "SUB1", 100.0, "C")]
        subtotals = [_subtotal("SUB1", 100.0, "D"), _subtotal("SUB1", 100.0, "C")]
        disc, _ = detect_inconsistencies(entries, subtotals, total_receitas=100.0, total_despesas=100.0)
        self.assertEqual([d for d in disc if d.level == "subcategory"], [])


class US1WritebackTest(unittest.TestCase):
    """US1/US2 — the SQL batch, alert shape, idempotency, summary, and resolution graft."""

    def test_consistent_writeback_is_lone_delete(self):
        entries = [_entry("E1", "SUB1", 100.0, "D")]
        subtotals = [_subtotal("SUB1", 100.0, "D")]
        res = build_consistency_writeback(PERIOD, entries, subtotals, 0.0, 100.0)
        self.assertEqual(res.discrepancies, [])
        self.assertIsNone(res.alert)
        self.assertIsNone(res.summary)
        alert_id = det_id("alert", PERIOD, ALERT_TYPE)
        self.assertEqual(res.sql.strip(), f'DELETE FROM "alerts" WHERE "id" = \'{alert_id}\';')
        self.assertNotIn("INSERT", res.sql)

    def test_inconsistent_writeback_clears_then_inserts(self):
        entries = [_entry("E1", "SUB1", 60.0, "D")]
        subtotals = [_subtotal("SUB1", 100.0, "D")]
        res = build_consistency_writeback(PERIOD, entries, subtotals, 0.0, 100.0)
        self.assertTrue(res.discrepancies)
        self.assertIsNotNone(res.alert)
        self.assertIsNotNone(res.summary)
        # Clear precedes insert (atomic batch).
        self.assertLess(res.sql.index("DELETE"), res.sql.index("INSERT OR REPLACE"))
        self.assertEqual(res.alert["type"], ALERT_TYPE)
        self.assertEqual(res.alert["severity"], ALERT_SEVERITY)
        self.assertEqual(res.alert["reference_period"], PERIOD)
        meta = json.loads(res.alert["metadata"])
        self.assertIn("E1", meta["entry_ids"])
        self.assertTrue(meta["checks"])
        self.assertEqual(meta["counts"]["subcategory"], 1)

    def test_idempotent_stable_id(self):
        entries = [_entry("E1", "SUB1", 60.0, "D")]
        subtotals = [_subtotal("SUB1", 100.0, "D")]
        a = build_consistency_writeback(PERIOD, entries, subtotals, 0.0, 100.0)
        b = build_consistency_writeback(PERIOD, entries, subtotals, 0.0, 100.0)
        self.assertEqual(a.alert["id"], b.alert["id"])
        self.assertEqual(a.alert["id"], det_id("alert", PERIOD, ALERT_TYPE))

    def test_resolution_graft_applied(self):
        entries = [_entry("E1", "SUB1", 60.0, "D")]
        subtotals = [_subtotal("SUB1", 100.0, "D")]
        prior = {"resolved": 1, "resolved_at": 1234, "notes": "known portal quirk"}
        res = build_consistency_writeback(PERIOD, entries, subtotals, 0.0, 100.0, prior_resolution=prior)
        self.assertEqual(res.alert["resolved"], 1)
        self.assertEqual(res.alert["resolved_at"], 1234)
        self.assertEqual(res.alert["notes"], "known portal quirk")

    def test_resolution_graft_default_when_no_prior(self):
        entries = [_entry("E1", "SUB1", 60.0, "D")]
        subtotals = [_subtotal("SUB1", 100.0, "D")]
        res = build_consistency_writeback(PERIOD, entries, subtotals, 0.0, 100.0, prior_resolution=None)
        self.assertEqual(res.alert["resolved"], 0)
        self.assertIsNone(res.alert["resolved_at"])
        self.assertIsNone(res.alert["notes"])

    def test_resolution_graft_ignored_when_prior_is_default(self):
        # A prior row with resolved=0 and no notes must NOT mark the new alert resolved.
        entries = [_entry("E1", "SUB1", 60.0, "D")]
        subtotals = [_subtotal("SUB1", 100.0, "D")]
        prior = {"resolved": 0, "resolved_at": None, "notes": None}
        res = build_consistency_writeback(PERIOD, entries, subtotals, 0.0, 100.0, prior_resolution=prior)
        self.assertEqual(res.alert["resolved"], 0)

    def test_sql_escaping_in_metadata(self):
        # An apostrophe anywhere serialized into the row must be doubled (no SQL break).
        entries = [_entry("E'1", "SUB1", 60.0, "D")]
        subtotals = [_subtotal("SUB1", 100.0, "D")]
        res = build_consistency_writeback(PERIOD, entries, subtotals, 0.0, 100.0)
        self.assertIn("E''1", res.sql)


if __name__ == "__main__":
    unittest.main()
