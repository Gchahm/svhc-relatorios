"""US2: the feature-028 reconciliation cascade hard-deletes a vanished row + its dependents (real D1).

Builds the SQL via the pure ``build_reconciliation`` (importable without playwright) and runs it
through the real ``d1.execute_sql`` — the same batch the scraper's ``_reconcile_period`` submits.
Simulates a re-scrape of the synthetic period where **E5** vanished from the portal.
"""

from __future__ import annotations

import unittest

from common import d1
from scraper.reconcile import ALERT_TYPE, ExistingRows, ScrapedIds, build_reconciliation

from . import _harness as h


class TestReconcileCascade(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        h.seed_once()  # full first-time provision (migrations + base data)
        cls.ids = h.ids()
        cls.period = cls.ids["period"]

    def setUp(self):
        h.restore()  # restore E5 + its attachment/state each test

    def _existing_and_scraped_without(self, dropped_keys):
        """Read the period's current mirror ids from D1; build a scrape set missing dropped_keys."""
        rid = self.ids["report_id"]
        ent_rows = h.q(f"SELECT id FROM entries WHERE report_id = '{rid}'")
        entry_ids = {r["id"] for r in ent_rows}
        att_rows = h.q(
            "SELECT id, entry_id FROM attachments WHERE entry_id IN "
            f"(SELECT id FROM entries WHERE report_id = '{rid}')"
        )
        existing = ExistingRows(
            entries=[{"id": r["id"]} for r in ent_rows],
            attachments=[{"id": r["id"], "entry_id": r["entry_id"]} for r in att_rows],
        )
        dropped_entry_ids = {self.ids["entries"][k] for k in dropped_keys}
        dropped_att_ids = {self.ids["attachments"][k] for k in dropped_keys if k in self.ids["attachments"]}
        scraped = ScrapedIds(
            entry_ids=entry_ids - dropped_entry_ids,
            attachment_ids={r["id"] for r in att_rows} - dropped_att_ids,
        )
        return existing, scraped

    def test_vanished_entry_cascades_and_alerts(self):
        e5 = self.ids["entries"]["E5"]
        e5_att = self.ids["attachments"]["E5"]
        # Preconditions.
        self.assertEqual(h.count("entries", f"id = '{e5}'"), 1)
        self.assertEqual(h.count("attachments", f"id = '{e5_att}'"), 1)
        self.assertEqual(h.count("attachment_state", f"attachment_id = '{e5_att}'"), 1)

        existing, scraped = self._existing_and_scraped_without(["E5"])
        result = build_reconciliation(self.period, existing, scraped)
        self.assertEqual(result.deleted_counts["entries"], 1)
        d1.execute_sql(result.sql, target="local")

        # Mirror row + analysis-owned dependents cascade-deleted.
        self.assertEqual(h.count("entries", f"id = '{e5}'"), 0)
        self.assertEqual(h.count("attachments", f"id = '{e5_att}'"), 0)
        self.assertEqual(h.count("attachment_state", f"attachment_id = '{e5_att}'"), 0)
        # A portal_row_vanished alert exists for the period.
        self.assertEqual(
            h.count("alerts", f"type = '{ALERT_TYPE}' AND reference_period = '{self.period}'"), 1
        )

    def test_idempotent_mirror_and_alert_lifecycle(self):
        e5 = self.ids["entries"]["E5"]
        # First reconcile (E5 vanished): hard-delete + fire the alert.
        existing, scraped = self._existing_and_scraped_without(["E5"])
        d1.execute_sql(build_reconciliation(self.period, existing, scraped).sql, target="local")
        self.assertEqual(h.count("entries", f"id = '{e5}'"), 0)
        self.assertEqual(
            h.count("alerts", f"type = '{ALERT_TYPE}' AND reference_period = '{self.period}'"), 1
        )

        # Second reconcile reads the mirror FRESH (E5 already gone): nothing is stale, so the
        # mirror stays deleted (idempotent) and the now-resolved alert is cleared (DELETE-only) —
        # this is the designed lifecycle, not a double-fire.
        existing2, scraped2 = self._existing_and_scraped_without(["E5"])
        self.assertNotIn(e5, {x["id"] for x in existing2.entries})  # E5 no longer in D1
        result2 = build_reconciliation(self.period, existing2, scraped2)
        self.assertEqual(sum(result2.deleted_counts.values()), 0)
        d1.execute_sql(result2.sql, target="local")
        self.assertEqual(h.count("entries", f"id = '{e5}'"), 0)
        self.assertEqual(
            h.count("alerts", f"type = '{ALERT_TYPE}' AND reference_period = '{self.period}'"), 0
        )

    def test_nothing_stale_clears_alert(self):
        # A consistent re-scrape (nothing dropped) issues only the clear-alert DELETE.
        existing, scraped = self._existing_and_scraped_without([])
        result = build_reconciliation(self.period, existing, scraped)
        self.assertEqual(sum(result.deleted_counts.values()), 0)
        d1.execute_sql(result.sql, target="local")
        # No vanished-row alert for the period (nothing stale).
        self.assertEqual(
            h.count("alerts", f"type = '{ALERT_TYPE}' AND reference_period = '{self.period}'"), 0
        )


if __name__ == "__main__":
    unittest.main()
