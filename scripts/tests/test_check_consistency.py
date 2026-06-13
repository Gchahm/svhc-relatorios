"""Tests for analysis.checks.consistency (TEST-002 / issue #69). Pure over PeriodData/RefIndex."""

import unittest

from analysis.checks.consistency import (
    check_balance_accumulated,
    check_balance_continuity,
    check_balance_month,
    check_duplicates,
    check_entries_vs_totals,
    check_large_expenses_no_attachment,
    check_missing_periods,
    check_negative_credits,
    check_new_vendors,
    check_subtotals,
    run_consistency,
)

from tests._fixtures import attachment, entry, make_period, make_refs, make_report


class BalanceMonthTest(unittest.TestCase):
    def test_consistent_silent(self):
        pd = make_period("2025-12", report=make_report(total_revenue=300.0, total_expenses=100.0, month_balance=200.0))
        self.assertEqual(check_balance_month(pd), [])

    def test_inconsistent_fires_critical(self):
        pd = make_period("2025-12", report=make_report(total_revenue=300.0, total_expenses=100.0, month_balance=150.0))
        alerts = check_balance_month(pd)
        self.assertEqual(len(alerts), 1)
        self.assertEqual(alerts[0].type, "balance_month_mismatch")
        self.assertEqual(alerts[0].severity, "critical")

    def test_within_tolerance_silent(self):
        pd = make_period("2025-12", report=make_report(total_revenue=300.0, total_expenses=100.0, month_balance=200.04))
        self.assertEqual(check_balance_month(pd), [])


class BalanceAccumulatedTest(unittest.TestCase):
    def test_inconsistent_fires(self):
        pd = make_period("2025-12", report=make_report(opening_balance=100.0, month_balance=50.0, accumulated_balance=200.0))
        alerts = check_balance_accumulated(pd)
        self.assertEqual(alerts[0].type, "balance_accumulated_mismatch")

    def test_consistent_silent(self):
        pd = make_period("2025-12", report=make_report(opening_balance=100.0, month_balance=50.0, accumulated_balance=150.0))
        self.assertEqual(check_balance_accumulated(pd), [])


class BalanceContinuityTest(unittest.TestCase):
    def test_first_period_silent(self):
        cur = make_period("2025-01")
        self.assertEqual(check_balance_continuity(cur, {"2025-01": cur}), [])

    def test_opening_mismatch_fires(self):
        prev = make_period("2025-01", report=make_report(accumulated_balance=500.0))
        cur = make_period("2025-02", report=make_report(opening_balance=499.0))
        alerts = check_balance_continuity(cur, {"2025-01": prev, "2025-02": cur})
        self.assertEqual(alerts[0].type, "balance_opening_mismatch")


class EntriesVsTotalsTest(unittest.TestCase):
    def test_matching_silent(self):
        entries = [entry("e1", amount=100.0, movement_type="D"), entry("e2", amount=50.0, movement_type="C")]
        pd = make_period("2025-12", report=make_report(total_expenses=100.0, total_revenue=50.0), entries=entries)
        self.assertEqual(check_entries_vs_totals(pd), [])

    def test_expense_mismatch_fires(self):
        entries = [entry("e1", amount=100.0, movement_type="D")]
        pd = make_period("2025-12", report=make_report(total_expenses=200.0), entries=entries)
        alerts = check_entries_vs_totals(pd)
        self.assertTrue(any(a.type == "entries_expenses_mismatch" for a in alerts))


class SubtotalsTest(unittest.TestCase):
    def test_mismatch_fires(self):
        entries = [entry("e1", amount=100.0, movement_type="D", subcategory_id="s1")]
        subtotals = [{"subcategory_id": "s1", "movement_type": "D", "amount": 150.0}]
        pd = make_period("2025-12", entries=entries, category_subtotals=subtotals)
        refs = make_refs(subcategories=[{"id": "s1", "name": "X", "category_id": "c"}],
                         categories=[{"id": "c", "name": "C"}])
        alerts = check_subtotals(pd, refs)
        self.assertEqual(alerts[0].type, "subtotal_mismatch")

    def test_match_silent(self):
        entries = [entry("e1", amount=100.0, movement_type="D", subcategory_id="s1")]
        subtotals = [{"subcategory_id": "s1", "movement_type": "D", "amount": 100.0}]
        pd = make_period("2025-12", entries=entries, category_subtotals=subtotals)
        self.assertEqual(check_subtotals(pd, make_refs()), [])


class DuplicatesTest(unittest.TestCase):
    def test_duplicate_fires(self):
        entries = [
            entry("e1", amount=10.0, date="2025-12-01", description="X", movement_type="D"),
            entry("e2", amount=10.0, date="2025-12-01", description="X", movement_type="D"),
        ]
        pd = make_period("2025-12", entries=entries)
        alerts = check_duplicates(pd)
        self.assertEqual(len(alerts), 1)
        self.assertEqual(alerts[0].type, "duplicate_entry")
        self.assertEqual(sorted(alerts[0].metadata["entry_ids"]), ["e1", "e2"])

    def test_unique_silent(self):
        entries = [entry("e1", amount=10.0, description="X"), entry("e2", amount=11.0, description="Y")]
        pd = make_period("2025-12", entries=entries)
        self.assertEqual(check_duplicates(pd), [])


class NegativeCreditsTest(unittest.TestCase):
    def test_fires(self):
        entries = [entry("e1", amount=-5.0, movement_type="C")]
        pd = make_period("2025-12", entries=entries)
        alerts = check_negative_credits(pd)
        self.assertEqual(alerts[0].type, "negative_credit")

    def test_none_silent(self):
        entries = [entry("e1", amount=5.0, movement_type="C")]
        pd = make_period("2025-12", entries=entries)
        self.assertEqual(check_negative_credits(pd), [])


class MissingPeriodsTest(unittest.TestCase):
    def test_gap_fires(self):
        prev = make_period("2025-01")
        cur = make_period("2025-03")  # 2025-02 missing
        alerts = check_missing_periods(cur, {"2025-01": prev, "2025-03": cur})
        self.assertEqual(alerts[0].type, "missing_period")
        self.assertIn("2025-02", alerts[0].metadata["missing"])

    def test_contiguous_silent(self):
        prev = make_period("2025-01")
        cur = make_period("2025-02")
        self.assertEqual(check_missing_periods(cur, {"2025-01": prev, "2025-02": cur}), [])


class LargeExpensesNoAttachmentTest(unittest.TestCase):
    def test_fires_for_large_undocumented(self):
        entries = [entry("e1", amount=2000.0, movement_type="D")]
        pd = make_period("2025-12", entries=entries, attachments=[])
        alerts = check_large_expenses_no_attachment(pd)
        self.assertEqual(alerts[0].type, "large_expense_no_attachment")

    def test_silent_when_documented(self):
        entries = [entry("e1", amount=2000.0, movement_type="D")]
        att = attachment("a1", "e1")
        pd = make_period("2025-12", entries=entries, attachments=[att])
        self.assertEqual(check_large_expenses_no_attachment(pd), [])

    def test_silent_below_threshold(self):
        entries = [entry("e1", amount=500.0, movement_type="D")]
        pd = make_period("2025-12", entries=entries)
        self.assertEqual(check_large_expenses_no_attachment(pd), [])


class NewVendorsTest(unittest.TestCase):
    def test_fires_for_first_seen(self):
        entries = [entry("e1", amount=100.0, vendor_id="v1")]
        pd = make_period("2025-12", entries=entries)
        refs = make_refs(vendors=[{"id": "v1", "name": "NEW"}], vendor_first_seen={"v1": "2025-12"})
        alerts = check_new_vendors(pd, refs)
        self.assertEqual(alerts[0].type, "new_vendor")

    def test_silent_for_existing(self):
        entries = [entry("e1", amount=100.0, vendor_id="v1")]
        pd = make_period("2025-12", entries=entries)
        refs = make_refs(vendors=[{"id": "v1", "name": "OLD"}], vendor_first_seen={"v1": "2025-01"})
        self.assertEqual(check_new_vendors(pd, refs), [])


class RunConsistencyTest(unittest.TestCase):
    def test_aggregates_without_raising(self):
        entries = [entry("e1", amount=100.0, movement_type="D", subcategory_id="s1")]
        pd = make_period("2025-12", report=make_report(total_expenses=100.0, month_balance=-100.0), entries=entries)
        out = run_consistency(pd, {"2025-12": pd}, make_refs())
        self.assertIsInstance(out, list)


if __name__ == "__main__":
    unittest.main()
