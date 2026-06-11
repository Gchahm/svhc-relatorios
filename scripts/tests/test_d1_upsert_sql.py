"""Tests for ``common.d1.upsert_sql`` and the refactored ``upsert_tables`` (feature 024 / issue #37).

Run from the repo root: ``python -m unittest discover -s scripts/tests -t scripts``
(``-t scripts`` puts ``scripts/`` on ``sys.path`` so ``common`` imports as a top-level package).
"""

import unittest

from common import d1


class UpsertSqlTest(unittest.TestCase):
    def _row(self):
        return {
            "id": "a1",
            "type": "duplicate_entry",
            "severity": "warning",
            "title": "t",
            "description": "d",
            "reference_period": "2025-12",
            "metadata": None,
            "resolved": 0,
            "resolved_at": None,
            "notes": None,
        }

    def test_returns_same_sql_as_build_sql(self):
        data = {"alerts": [self._row()]}
        self.assertEqual(d1.upsert_sql(data), d1.build_sql(data)[0])

    def test_contains_insert_for_table(self):
        sql = d1.upsert_sql({"alerts": [self._row()]})
        self.assertIn('INSERT OR REPLACE INTO "alerts"', sql)

    def test_empty_dataset_returns_empty_string(self):
        self.assertEqual(d1.upsert_sql({}), "")
        self.assertEqual(d1.upsert_sql({"alerts": []}), "")

    def test_upsert_tables_submits_upsert_sql_and_returns_counts(self):
        captured = {}

        def fake_execute(sql, *, target):
            captured["sql"] = sql
            captured["target"] = target

        orig = d1.execute_sql
        d1.execute_sql = fake_execute
        try:
            data = {"alerts": [self._row()]}
            counts = d1.upsert_tables(data, target="local")
        finally:
            d1.execute_sql = orig

        self.assertEqual(counts, {"alerts": 1})
        self.assertEqual(captured["sql"], d1.upsert_sql(data))
        self.assertEqual(captured["target"], "local")

    def test_upsert_tables_empty_does_not_execute(self):
        calls = []

        def fake_execute(sql, *, target):
            calls.append(sql)

        orig = d1.execute_sql
        d1.execute_sql = fake_execute
        try:
            counts = d1.upsert_tables({"alerts": []}, target="local")
        finally:
            d1.execute_sql = orig

        self.assertEqual(counts, {})
        self.assertEqual(calls, [])


if __name__ == "__main__":
    unittest.main()
