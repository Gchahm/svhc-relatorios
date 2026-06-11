"""Tests for the analysis-owned attachment_state table (BUG-002 / issue #33).

Covers the three seams that moved classification state off the mirror table `attachments`:

- ``select_work`` pending semantics read ``classified_at`` (supplied by the loader's LEFT JOIN
  on ``attachment_state``): None ⇒ pending, set ⇒ classified (contract C2).
- ``_merge_and_write`` stamps ``attachment_state`` (not ``attachments``) in the same atomic
  batch as the analysis insert (contract C3) — the cross-table absence is asserted here and the
  ordering/atomicity in test_attachment_writeback_atomic.py.
- ``mark_pending`` clears ``attachment_state`` only and never writes ``attachments`` (contract C4),
  resolving an entry-id scope to attachment ids via a read-only subquery.

Run: ``python -m unittest discover -s scripts/tests -t scripts``
"""

import unittest

from analysis import attachments as attachments_mod
from analysis import extractions as extractions_mod
from analysis.attachments import AttachmentAnalysisResult, _merge_and_write, select_work
from analysis.extractions import mark_pending
from analysis.models import PeriodData


def _attachment(aid, entry_id, *, classified_at):
    return {
        "id": aid,
        "entry_id": entry_id,
        "file_path": f"2025-12/{entry_id}_p1.png",
        "content_hash": f"hash-{aid}",  # distinct → each its own singleton group
        "classified_at": classified_at,
    }


def _period(attachments):
    entries = [{"id": d["entry_id"], "amount": 100.0} for d in attachments]
    return {
        "2025-12": PeriodData(
            period="2025-12",
            raw={},
            report={},
            entries=entries,
            category_subtotals=[],
            attachments=attachments,
        )
    }


class SelectWorkPendingTest(unittest.TestCase):
    def test_none_classified_at_is_pending(self):
        periods = _period([_attachment("att-1", "ent-1", classified_at=None)])
        work = select_work(periods)
        self.assertEqual([w.attachment["id"] for w in work], ["att-1"])

    def test_set_classified_at_is_excluded(self):
        periods = _period([_attachment("att-1", "ent-1", classified_at=1_700_000_000_000)])
        work = select_work(periods)
        self.assertEqual(work, [])

    def test_mixed(self):
        periods = _period(
            [
                _attachment("att-1", "ent-1", classified_at=None),
                _attachment("att-2", "ent-2", classified_at=1_700_000_000_000),
                _attachment("att-3", "ent-3", classified_at=None),
            ]
        )
        work = select_work(periods)
        self.assertEqual(sorted(w.attachment["id"] for w in work), ["att-1", "att-3"])


class MergeWriteTargetsStateTest(unittest.TestCase):
    def test_stamp_targets_attachment_state_not_attachments(self):
        captured = []
        orig = attachments_mod.d1.execute_sql
        attachments_mod.d1.execute_sql = lambda sql, *, target: captured.append(sql)
        try:
            _merge_and_write(
                AttachmentAnalysisResult(
                    attachment_id="att-1",
                    entry_id="ent-1",
                    entry_amount=100.0,
                    extracted_amount=100.0,
                    amount_match=True,
                ),
                target="local",
            )
        finally:
            attachments_mod.d1.execute_sql = orig

        self.assertEqual(len(captured), 1)
        sql = captured[0]
        self.assertIn("INSERT INTO attachment_state (attachment_id, classified_at)", sql)
        self.assertIn("ON CONFLICT(attachment_id) DO UPDATE SET classified_at = excluded.classified_at", sql)
        self.assertNotIn("UPDATE attachments SET", sql)


class MarkPendingTargetsStateTest(unittest.TestCase):
    def _capture(self, **kwargs):
        captured = []
        orig = extractions_mod.d1.execute_sql
        extractions_mod.d1.execute_sql = lambda sql, *, target: captured.append(sql)
        try:
            n = mark_pending("local", **kwargs)
        finally:
            extractions_mod.d1.execute_sql = orig
        return n, captured

    def test_attachment_ids_update_state_only(self):
        n, captured = self._capture(attachment_ids=["att-1", "att-2"])
        self.assertEqual(n, 2)
        self.assertEqual(len(captured), 1)
        sql = captured[0]
        self.assertIn("UPDATE attachment_state SET classified_at = NULL", sql)
        self.assertIn("attachment_id IN ('att-1','att-2')", sql)
        self.assertNotIn("UPDATE attachments SET", sql)

    def test_entry_ids_resolve_to_attachment_ids_via_readonly_subquery(self):
        n, captured = self._capture(entry_ids=["ent-9"])
        self.assertEqual(n, 1)
        sql = captured[0]
        self.assertIn("UPDATE attachment_state SET classified_at = NULL", sql)
        self.assertIn("SELECT id FROM attachments WHERE entry_id IN ('ent-9')", sql)
        # The only `attachments` reference is the read-only subquery — no write to the mirror.
        self.assertNotIn("UPDATE attachments", sql)

    def test_no_ids_is_noop(self):
        n, captured = self._capture()
        self.assertEqual(n, 0)
        self.assertEqual(captured, [])


if __name__ == "__main__":
    unittest.main()
