"""Tests for the atomic alerts writebacks (feature 024 / issue #37).

Drives ``analysis.run_analysis`` with all heavy collaborators stubbed (loader, checks, documents,
image materialization, summary) and the D1 seam intercepted, so the test exercises ONLY the
writeback sequencing. Asserts each per-period scope and the global overpayment scope are written
in ONE batch (DELETE + INSERT, or DELETE-only when empty), a failure propagates without a second
committed call for that scope, and grafted resolution/notes survive into the INSERT SQL.

Run: ``python -m unittest discover -s scripts/tests -t scripts``
"""

import unittest

import analysis
from analysis import run_analysis
from analysis.models import Alert, PeriodData


class _Boom(Exception):
    pass


def _alert(aid, period, type_="duplicate_entry"):
    return Alert(
        id=aid,
        type=type_,
        severity="warning",
        title="t",
        description="d",
        reference_period=period,
    )


class _Patches:
    """Context manager that stubs run_analysis's collaborators and records D1 writes."""

    def __init__(self, period_alerts, overpayment_alerts, prior_resolution=None, fail_on=None, periods=None):
        self.period_alerts = period_alerts  # {period: [Alert,...]} returned by run_all_checks
        self.overpayment_alerts = overpayment_alerts  # [Alert,...]
        self.prior_resolution = prior_resolution or []  # rows returned by d1.query
        self.fail_on = fail_on  # substring; execute_sql raises when sql contains it
        # Periods "loaded" from D1. Defaults to the alert keys, but can be set independently so the
        # overpayment-only case still loads a period (an empty load short-circuits run_analysis).
        self.periods = periods if periods is not None else list(period_alerts)
        self.executed = []  # list of (sql)
        self._orig = {}

    def __enter__(self):
        periods = {p: PeriodData(p, {}, {}, [], [], []) for p in self.periods}

        def fake_execute(sql, *, target):
            self.executed.append(sql)
            if self.fail_on and self.fail_on in sql:
                raise _Boom("simulated D1 failure")

        def fake_query(sql, *, target):
            return list(self.prior_resolution)

        self._patch(analysis, "load_all_periods", lambda target, f=None: (periods, object()))
        self._patch(analysis, "build_documents", lambda *, target: (0, 0))
        self._patch(analysis, "materialize_period_images", lambda *a, **k: None)
        self._patch(analysis, "run_all_checks", lambda periods_, refs: dict(self.period_alerts))
        self._patch(analysis, "check_document_overpayment", lambda *, target: list(self.overpayment_alerts))
        self._patch(analysis, "print_summary", lambda *a, **k: None)
        self._patch(analysis.d1, "execute_sql", fake_execute)
        self._patch(analysis.d1, "query", fake_query)
        return self

    def _patch(self, obj, name, value):
        self._orig[(obj, name)] = getattr(obj, name)
        setattr(obj, name, value)

    def __exit__(self, *exc):
        for (obj, name), value in self._orig.items():
            setattr(obj, name, value)
        return False

    def sqls_for(self, substr):
        return [s for s in self.executed if substr in s]


class AlertWritebackAtomicTest(unittest.TestCase):
    def test_period_writeback_is_single_batch_with_delete_and_insert(self):
        with _Patches({"2025-12": [_alert("a1", "2025-12")]}, []) as p:
            run_analysis(target="local")
        period_sqls = p.sqls_for("reference_period = '2025-12'")
        self.assertEqual(len(period_sqls), 1)
        self.assertIn("DELETE FROM alerts WHERE reference_period = '2025-12'", period_sqls[0])
        self.assertIn('INSERT OR REPLACE INTO "alerts"', period_sqls[0])

    def test_period_writeback_empty_is_delete_only_single_call(self):
        with _Patches({"2025-12": []}, []) as p:
            run_analysis(target="local")
        period_sqls = p.sqls_for("reference_period = '2025-12'")
        self.assertEqual(len(period_sqls), 1)
        self.assertIn("DELETE FROM alerts WHERE reference_period = '2025-12'", period_sqls[0])
        self.assertNotIn('INSERT OR REPLACE INTO "alerts"', period_sqls[0])

    def test_overpayment_writeback_is_single_batch(self):
        # Load a period (no per-period alerts) so run_analysis does not short-circuit, and focus on
        # the global overpayment writeback.
        with _Patches({}, [_alert("op1", "2025-12", type_="document_overpayment")], periods=["2025-12"]) as p:
            run_analysis(target="local")
        op_sqls = p.sqls_for("type = 'document_overpayment'")
        self.assertEqual(len(op_sqls), 1)
        self.assertIn("DELETE FROM alerts WHERE type = 'document_overpayment'", op_sqls[0])
        self.assertIn('INSERT OR REPLACE INTO "alerts"', op_sqls[0])

    def test_period_failure_propagates_with_single_scope_call(self):
        with _Patches(
            {"2025-12": [_alert("a1", "2025-12")]}, [], fail_on="reference_period = '2025-12'"
        ) as p:
            with self.assertRaises(_Boom):
                run_analysis(target="local")
            # Only the one combined batch was attempted for the scope — no standalone delete that
            # could have wiped the period's prior alerts without reinserting.
            self.assertEqual(len(p.sqls_for("reference_period = '2025-12'")), 1)

    def test_grafted_resolution_survives_into_insert_sql(self):
        prior = [{"id": "a1", "resolved": 1, "resolved_at": 123, "notes": "checked"}]
        with _Patches({"2025-12": [_alert("a1", "2025-12")]}, [], prior_resolution=prior) as p:
            run_analysis(target="local")
        period_sqls = p.sqls_for("reference_period = '2025-12'")
        self.assertEqual(len(period_sqls), 1)
        # The grafted user disposition (resolved=1, notes) must be present in the reinserted row.
        self.assertIn("checked", period_sqls[0])


if __name__ == "__main__":
    unittest.main()
