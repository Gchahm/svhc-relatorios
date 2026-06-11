"""Tests for authoritative re-scrape portal-deletion reconciliation (BUG-004 / issue #35).

The pure ``build_reconciliation`` diffs the freshly-scraped row set against what D1 holds for a
period and produces a single atomic SQL batch that hard-deletes the vanished mirror rows, cascade-
cleans their analysis-owned dependents, and raises one idempotent ``critical`` ``portal_row_vanished``
alert with the vanished rows' frozen values. Covers (per the spec's user stories):

- US1 — re-scrape makes the mirror exact: stale-row diff + mirror DELETEs; no-op when identical;
  subtotals/approvers diffed; surviving rows untouched (FR-001/002/005, SC-001/005).
- US2 — vanished-row critical alert with frozen evidence: idempotent per-period id, one atomic
  batch (deletes + alert), SQL escaping (FR-006/007/009, SC-002/003).
- US3 — cascade-clean analysis-owned dependents: entry-gone forces its attachment stale; an
  independently-stale attachment is still cleaned (FR-003/004, SC-004).

Run: ``python -m unittest discover -s scripts/tests -t scripts``
"""

import json
import unittest

from common import det_id
from scraper.reconcile import (
    ALERT_SEVERITY,
    ALERT_TYPE,
    ExistingRows,
    ReconcileResult,
    ScrapedIds,
    build_reconciliation,
)

PERIOD = "2026-01"


def _entry(eid, *, date="2026-01-15", description="X", amount=10.0):
    return {"id": eid, "date": date, "description": description, "amount": amount}


def _att(aid, entry_id):
    return {"id": aid, "entry_id": entry_id}


class US1MirrorMatchTest(unittest.TestCase):
    """US1 — re-scrape makes the mirror exactly match the portal."""

    def test_noop_when_identical(self):
        existing = ExistingRows(
            entries=[_entry("E1"), _entry("E2")],
            attachments=[_att("A1", "E1")],
            subtotal_ids={"S1"},
            approver_ids={"P1"},
        )
        scraped = ScrapedIds(
            entry_ids={"E1", "E2"}, attachment_ids={"A1"}, subtotal_ids={"S1"}, approver_ids={"P1"}
        )
        res = build_reconciliation(PERIOD, existing, scraped)
        self.assertEqual(res.deleted_counts, {"entries": 0, "attachments": 0, "category_subtotals": 0, "approvers": 0})
        self.assertIsNone(res.alert)
        # No mirror deletes; only the clear-only alert DELETE (idempotency) remains.
        self.assertNotIn('DELETE FROM "entries"', res.sql)
        self.assertNotIn('DELETE FROM "attachments"', res.sql)
        self.assertNotIn("INSERT OR REPLACE INTO \"alerts\"", res.sql)
        self.assertIn(f'DELETE FROM "alerts" WHERE "type" = \'{ALERT_TYPE}\'', res.sql)

    def test_stale_entry_diffed(self):
        existing = ExistingRows(entries=[_entry("E1"), _entry("E2"), _entry("E3", description="ghost", amount=99.5)])
        scraped = ScrapedIds(entry_ids={"E1", "E2"})
        res = build_reconciliation(PERIOD, existing, scraped)
        self.assertEqual(res.deleted_counts["entries"], 1)
        self.assertIn('DELETE FROM "entries" WHERE "id" IN (\'E3\')', res.sql)
        # Frozen evidence recorded in the alert.
        meta = json.loads(res.alert["metadata"])
        self.assertEqual(meta["entry_ids"], ["E3"])
        self.assertEqual(meta["deleted_entries"][0]["id"], "E3")
        self.assertEqual(meta["deleted_entries"][0]["description"], "ghost")
        self.assertEqual(meta["deleted_entries"][0]["amount"], 99.5)

    def test_subtotals_and_approvers_diffed(self):
        existing = ExistingRows(subtotal_ids={"S1", "S2"}, approver_ids={"P1"})
        scraped = ScrapedIds(subtotal_ids={"S1"}, approver_ids=set())
        res = build_reconciliation(PERIOD, existing, scraped)
        self.assertEqual(res.deleted_counts["category_subtotals"], 1)
        self.assertEqual(res.deleted_counts["approvers"], 1)
        self.assertIn('DELETE FROM "category_subtotals" WHERE "id" IN (\'S2\')', res.sql)
        self.assertIn('DELETE FROM "approvers" WHERE "id" IN (\'P1\')', res.sql)
        self.assertIsNotNone(res.alert)

    def test_surviving_rows_untouched(self):
        existing = ExistingRows(entries=[_entry("E1"), _entry("E2"), _entry("E3")])
        scraped = ScrapedIds(entry_ids={"E1", "E2"})
        res = build_reconciliation(PERIOD, existing, scraped)
        # Surviving ids never appear in any delete id-list.
        self.assertNotIn("'E1'", res.sql)
        self.assertNotIn("'E2'", res.sql)
        self.assertIn("'E3'", res.sql)


class US2VanishedAlertTest(unittest.TestCase):
    """US2 — idempotent critical alert with frozen evidence, in one atomic batch."""

    def test_alert_idempotent_id(self):
        existing = ExistingRows(entries=[_entry("E3")])
        scraped = ScrapedIds(entry_ids=set())
        res = build_reconciliation(PERIOD, existing, scraped)
        self.assertEqual(res.alert["id"], det_id("alert", PERIOD, ALERT_TYPE))
        self.assertEqual(res.alert["type"], ALERT_TYPE)
        self.assertEqual(res.alert["severity"], ALERT_SEVERITY)
        # The prior per-period alert is always cleared before the insert.
        clear_idx = res.sql.index(f'DELETE FROM "alerts" WHERE "type" = \'{ALERT_TYPE}\'')
        insert_idx = res.sql.index('INSERT OR REPLACE INTO "alerts"')
        self.assertLess(clear_idx, insert_idx)

    def test_atomic_single_batch(self):
        existing = ExistingRows(entries=[_entry("E3")])
        scraped = ScrapedIds(entry_ids=set())
        res = build_reconciliation(PERIOD, existing, scraped)
        self.assertIsInstance(res.sql, str)
        self.assertTrue(res.sql.startswith("PRAGMA defer_foreign_keys = ON;"))
        self.assertIn('DELETE FROM "alerts"', res.sql)
        self.assertIn('INSERT OR REPLACE INTO "alerts"', res.sql)

    def test_escaping(self):
        existing = ExistingRows(entries=[_entry("E'3", description="O'Brien")])
        scraped = ScrapedIds(entry_ids=set())
        res = build_reconciliation(PERIOD, existing, scraped)
        # The single quote in the id is doubled in the DELETE id-list.
        self.assertIn("'E''3'", res.sql)
        # And in the alert metadata JSON literal.
        self.assertIn("O''Brien", res.sql)


class US3CascadeTest(unittest.TestCase):
    """US3 — cascade-clean analysis-owned dependents of a removed mirror row."""

    def test_stale_entry_cascades_attachment(self):
        # The scrape still lists A3's id, but its owning entry E3 vanished — entry-gone wins.
        existing = ExistingRows(entries=[_entry("E3")], attachments=[_att("A3", "E3")])
        scraped = ScrapedIds(entry_ids=set(), attachment_ids={"A3"})
        res = build_reconciliation(PERIOD, existing, scraped)
        self.assertEqual(res.deleted_counts["attachments"], 1)
        self.assertIn('DELETE FROM "attachment_analysis_records" WHERE "attachment_analysis_id" IN', res.sql)
        self.assertIn('DELETE FROM "attachment_analyses" WHERE "attachment_id" IN (\'A3\')', res.sql)
        self.assertIn('DELETE FROM "attachment_state" WHERE "attachment_id" IN (\'A3\')', res.sql)
        self.assertIn('DELETE FROM "page_classifications" WHERE "attachment_id" IN (\'A3\')', res.sql)
        self.assertIn('DELETE FROM "document_entries"', res.sql)
        self.assertIn('"source_attachment_id" IN (\'A3\')', res.sql)
        self.assertIn('"entry_id" IN (\'E3\')', res.sql)
        self.assertIn('DELETE FROM "attachments" WHERE "id" IN (\'A3\')', res.sql)

    def test_independent_stale_attachment(self):
        # A3 is gone from the scrape but its entry E1 survives — still cascade-cleaned.
        existing = ExistingRows(entries=[_entry("E1")], attachments=[_att("A3", "E1")])
        scraped = ScrapedIds(entry_ids={"E1"}, attachment_ids=set())
        res = build_reconciliation(PERIOD, existing, scraped)
        self.assertEqual(res.deleted_counts["entries"], 0)
        self.assertEqual(res.deleted_counts["attachments"], 1)
        self.assertIn('DELETE FROM "attachments" WHERE "id" IN (\'A3\')', res.sql)
        self.assertIn('DELETE FROM "attachment_state" WHERE "attachment_id" IN (\'A3\')', res.sql)
        # No entry delete since E1 survives.
        self.assertNotIn('DELETE FROM "entries"', res.sql)
        # document_entries cleaned by source_attachment_id only (no stale entry).
        self.assertIn('"source_attachment_id" IN (\'A3\')', res.sql)

    def test_returns_reconcileresult(self):
        res = build_reconciliation(PERIOD, ExistingRows(), ScrapedIds())
        self.assertIsInstance(res, ReconcileResult)


if __name__ == "__main__":
    unittest.main()
