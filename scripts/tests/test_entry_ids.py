"""Tests for order-independent deterministic entry-id derivation (issue #40 / IMP-003).

The pure ``entry_ids`` module assigns each scraped ledger line a deterministic id whose
disambiguating component prefers an order-independent portal-native discriminator (the entry's
``documento_ids`` set) over the legacy order-dependent occurrence index. Covers (per the spec):

- US1 — stable ids for distinct-doc duplicates + no churn for singletons (FR-001/002/004,
  SC-001/002/005).
- US2 — occurrence-index fallback is logged for no-doc / shared-doc duplicate groups, and NOT for
  doc-distinguished groups; ids stay unique within a group (FR-003/005, FR-007, SC-003).
- US3 — id drift on re-scrape is detected; reproduced ids and first scrape yield none
  (FR-006, SC-004).

Run: ``python -m unittest discover -s scripts/tests -t scripts``
"""

import unittest

from common import det_id
from scraper.entry_ids import (
    AssignResult,
    EntryKeyInput,
    ScrapedEntry,
    assign_entry_ids,
    detect_id_drift,
    entry_discriminator,
)

PERIOD = "2026-01"
SUB = "5d1ae03c-7f83-5f1a-8726-90df7aa489ea"
DATE = "2026-01-20"
DESC = "ENERGIA ELÉTRICA - ENERGIA ELÉTRICA"
AMT = 101.76


def _row(documento_ids=None, *, date=DATE, desc=DESC, amount=AMT, sub=SUB):
    return EntryKeyInput(date, desc, amount, sub, list(documento_ids or []))


def _by_doc(rows, result: AssignResult):
    """Map first-doc-id → assigned entry_id, for order-independence comparison."""
    return {r.documento_ids[0]: a.entry_id for r, a in zip(rows, result.assigned)}


class TestDiscriminator(unittest.TestCase):
    def test_empty_is_none(self):
        self.assertIsNone(entry_discriminator([]))

    def test_order_independent_and_deduped(self):
        self.assertEqual(entry_discriminator([3, 1, 2]), entry_discriminator([2, 3, 1]))
        self.assertEqual(entry_discriminator([1, 1, 2]), "doc:1,2")


class TestUS1StableAndNoChurn(unittest.TestCase):
    def test_singleton_id_matches_legacy(self):
        """A unique natural key keeps the legacy det_id(..., '1') — zero churn (SC-002)."""
        rows = [_row([18990374])]
        res = assign_entry_ids(PERIOD, rows)
        legacy = det_id("entry", PERIOD, DATE, DESC, str(AMT), SUB, "1")
        self.assertEqual(res.assigned[0].entry_id, legacy)
        self.assertEqual(res.assigned[0].discriminator, "1")
        self.assertFalse(res.assigned[0].used_fallback)
        self.assertEqual(res.fallback_notes, [])

    def test_singleton_without_docs_also_legacy(self):
        rows = [_row([])]
        res = assign_entry_ids(PERIOD, rows)
        self.assertEqual(res.assigned[0].entry_id, det_id("entry", PERIOD, DATE, DESC, str(AMT), SUB, "1"))

    def test_distinct_doc_duplicates_order_independent(self):
        """The real ENERGIA ELÉTRICA case: 3 identical charges, distinct doc ids (SC-001/005)."""
        rows = [_row([18990374]), _row([18990375]), _row([18990376])]
        fwd = assign_entry_ids(PERIOD, rows)
        rev = assign_entry_ids(PERIOD, list(reversed(rows)))
        self.assertEqual(_by_doc(rows, fwd), _by_doc(list(reversed(rows)), rev))
        # No fallback used, no notes, all ids unique.
        self.assertFalse(any(a.used_fallback for a in fwd.assigned))
        self.assertEqual(fwd.fallback_notes, [])
        self.assertEqual(len({a.entry_id for a in fwd.assigned}), 3)

    def test_distinct_doc_duplicate_id_is_doc_keyed(self):
        rows = [_row([18990374]), _row([18990375])]
        res = assign_entry_ids(PERIOD, rows)
        self.assertEqual(
            res.assigned[0].entry_id,
            det_id("entry", PERIOD, DATE, DESC, str(AMT), SUB, "doc:18990374"),
        )


class TestUS2Fallback(unittest.TestCase):
    def test_no_doc_duplicates_fall_back_with_one_note(self):
        rows = [_row([]), _row([])]
        res = assign_entry_ids(PERIOD, rows)
        self.assertTrue(all(a.used_fallback for a in res.assigned))
        self.assertEqual(len(res.fallback_notes), 1)
        self.assertIn(PERIOD, res.fallback_notes[0])
        self.assertIn("count=2", res.fallback_notes[0])
        # Still unique within the group.
        self.assertEqual(len({a.entry_id for a in res.assigned}), 2)
        self.assertEqual(res.assigned[0].discriminator, "1")
        self.assertEqual(res.assigned[1].discriminator, "2")

    def test_distinct_doc_group_emits_no_note(self):
        rows = [_row([1]), _row([2])]
        res = assign_entry_ids(PERIOD, rows)
        self.assertEqual(res.fallback_notes, [])

    def test_shared_single_doc_split_falls_back_and_stays_unique(self):
        """Two rows sharing ONE invoice (a real line-item split): doc set ties, index disambiguates."""
        rows = [_row([99]), _row([99])]
        res = assign_entry_ids(PERIOD, rows)
        self.assertTrue(all(a.used_fallback for a in res.assigned))
        self.assertEqual(len(res.fallback_notes), 1)
        self.assertEqual(len({a.entry_id for a in res.assigned}), 2)
        self.assertEqual(res.assigned[0].discriminator, "doc:99#1")
        self.assertEqual(res.assigned[1].discriminator, "doc:99#2")

    def test_mixed_group_distinct_doc_member_stable_only_others_fallback(self):
        """One distinct-doc member + two no-doc members: only the no-doc bucket falls back."""
        distinct = _row([7])
        nodoc_a = _row([])
        nodoc_b = _row([])
        rows = [distinct, nodoc_a, nodoc_b]
        res = assign_entry_ids(PERIOD, rows)
        self.assertFalse(res.assigned[0].used_fallback)
        self.assertTrue(res.assigned[1].used_fallback)
        self.assertTrue(res.assigned[2].used_fallback)
        # The distinct-doc member is order-independent: reversing keeps its id.
        rev_rows = [nodoc_b, nodoc_a, distinct]
        rev = assign_entry_ids(PERIOD, rev_rows)
        self.assertEqual(res.assigned[0].entry_id, rev.assigned[2].entry_id)
        # Exactly one note for the group.
        self.assertEqual(len(res.fallback_notes), 1)

    def test_singletons_across_different_keys_never_fall_back(self):
        rows = [_row([], desc="A"), _row([], desc="B")]
        res = assign_entry_ids(PERIOD, rows)
        self.assertEqual(res.fallback_notes, [])
        self.assertFalse(any(a.used_fallback for a in res.assigned))


class TestUS3Drift(unittest.TestCase):
    def _existing(self, entry_id):
        return [{"id": entry_id, "date": DATE, "description": DESC, "amount": AMT, "subcategory_id": SUB}]

    def test_first_scrape_no_drift(self):
        scraped = [ScrapedEntry("new-id", DATE, DESC, AMT, SUB)]
        self.assertEqual(detect_id_drift(PERIOD, scraped, []), [])

    def test_reproduced_id_no_drift(self):
        same = det_id("entry", PERIOD, DATE, DESC, str(AMT), SUB, "1")
        scraped = [ScrapedEntry(same, DATE, DESC, AMT, SUB)]
        self.assertEqual(detect_id_drift(PERIOD, scraped, self._existing(same)), [])

    def test_moved_id_flagged_once(self):
        old = "old-id-aaaa"
        new = det_id("entry", PERIOD, DATE, DESC, str(AMT), SUB, "doc:18990374")
        scraped = [ScrapedEntry(new, DATE, DESC, AMT, SUB)]
        notes = detect_id_drift(PERIOD, scraped, self._existing(old))
        self.assertEqual(len(notes), 1)
        self.assertIn(old, notes[0])
        self.assertIn(new, notes[0])

    def test_new_natural_key_is_not_drift(self):
        """A genuinely new entry (its natural key never existed) is not drift — it's an addition."""
        scraped = [ScrapedEntry("brand-new", "2026-01-22", "SOMETHING ELSE", 5.0, SUB)]
        notes = detect_id_drift(PERIOD, scraped, self._existing("old-id"))
        self.assertEqual(notes, [])


if __name__ == "__main__":
    unittest.main()
