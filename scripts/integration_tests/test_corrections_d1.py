"""Real-D1 integration tests for the data-correction audit trail (feature 054 / TRIAGE-003).

Drive the full ``apply_correction`` / ``list_corrections`` / ``undo_correction`` flow against local
Miniflare D1 (the real ``scripts/common/d1.py`` wrapper, the real staging-driven apply + analyze
pipeline), on the synthetic ``2099-01`` period. Smoke depth (one happy path + the distinct failure
paths) — the granular logic is covered by the fast mocked unit suite
(``scripts/tests/test_corrections.py``); this layer only proves the unstubbed wiring. Four tests:

- ``test_applied_lifecycle_record_list_durability_undo`` (US1/US2/US3): one pipeline pass for the
  whole applied-correction lifecycle — a verify-after-PASS correction persists the change + an
  ``applied`` row with all required fields; list returns them; the record survives an ephemeral-cache
  wipe (SC-004); undo restores the pre-correction value (SC-003) with ``reverted``/``reverted_by``/
  ``reverted_at`` and the original finding reappears; a second undo is rejected (FR-008).
- ``test_apply_fail_rolls_back_byte_for_byte`` (US1): a correction whose verify-after FAILS (target
  not cleared) rolls the data back byte-for-byte (SC-002) and records ``rolled-back``.
- ``test_no_op_writes_no_row`` / ``test_unverifiable_writes_no_row`` (US1): the no-op + unverifiable
  (fail-closed) paths write no row.

Run: ``pnpm test:py:integration`` (needs ``wrangler`` + an applied local migration set).
"""

from __future__ import annotations

import shutil
import tempfile
import unittest

from analysis import corrections
from analysis.corrections import apply_correction, list_corrections, undo_correction
from analysis.extractions import apply_extractions, mark_pending, summarize_mismatches
from analysis.page_classifications import record_classification
from analysis.verdicts import mismatch_key

from . import _harness as h


def _fields(valor_total):
    """A frozen-contract NFS-e page extraction with a given total (other amounts track it)."""
    return {
        "papel_artefato": "nfse",
        "tipo_documento": "NFS-e",
        "valor_total": valor_total,
        "valor_liquido": valor_total,
        "valor_pago": valor_total,
        "cnpj_emitente": "11222333000181",
        "nome_emitente": "EXEMPLO Fornecedor B",
        "data_emissao": "2099-01-10",
        "numero_documento": "NF-1002",
        "descricao_servico": "EXEMPLO servico",
    }


class TestCorrectionsD1(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        h.seed_once()
        cls.ids = h.ids()

    @classmethod
    def tearDownClass(cls):
        # These tests mutate shared synthetic state (E3's analysis + E4 gets visited by the period-
        # scoped propagation; alerts are rewritten). The integration suite runs all modules in ONE
        # process, so reset the baseline + drop our correction rows so later modules see a clean seed.
        h.restore()
        ids = h.ids()
        att_ids = ",".join(f"'{a}'" for a in ids["attachments"].values())
        h.q(f"DELETE FROM data_corrections WHERE attachment_id IN ({att_ids})")

    def setUp(self):
        # E3 is a singleton (no shared-NF sibling), ledger amount 250.00 — a clean correction target.
        # No per-test restore(): each test fully re-establishes E3 via _stage_and_propagate
        # (mark_pending invalidates staging → record → apply rolls up), every assertion is E3-scoped,
        # and run_analysis rewrites the 2099-01 alerts atomically (no cross-test accumulation). The
        # baseline reset for later modules in the shared process stays in tearDownClass.
        self.att = self.ids["attachments"]["E3"]
        self.entry = self.ids["entries"]["E3"]
        self.period = self.ids["period"]
        self._cache = tempfile.mkdtemp()
        # Clean any correction rows a prior test left for this attachment (data_corrections is outside
        # the synthetic analysis-owned reset set).
        h.q(f"DELETE FROM data_corrections WHERE attachment_id = '{self.att}'")

    # -- helpers ----------------------------------------------------------------

    def _stage_and_propagate(self, valor_total):
        """Put E3 into a known classified state with a given extracted total, via the real pipeline."""
        mark_pending("local", attachment_ids=[self.att])
        record_classification(self.att, "p1", _fields(valor_total), target="local")
        apply_extractions(target="local", periods_filter=[self.period], cache_dir=self._cache)

    def _amount_finding_key(self):
        """The amount mismatch_key for E3 as summarize_mismatches currently sees it (or None)."""
        rows = summarize_mismatches(target="local", cache_dir=self._cache, attachment_ids=[self.att])
        for m in rows:
            if m.get("kind") == "amount":
                return mismatch_key(m)
        return None

    def _extracted_amount(self):
        return h.scalar(f"SELECT extracted_amount FROM attachment_analyses WHERE attachment_id = '{self.att}'")

    # -- US1/US2/US3: the full applied-correction lifecycle in one pipeline pass -
    # Record (verify-after PASS) → list + audit row → cache-wipe durability (SC-004) →
    # undo (SC-003) → second-undo rejection (FR-008). Replaces four tests that each re-ran the same
    # arrange; the granular logic is covered by the mocked unit suite (scripts/tests/test_corrections.py).
    def test_applied_lifecycle_record_list_durability_undo(self):
        # Arrange: a wrong extraction (800) creates an amount mismatch vs the ledger's 250.
        self._stage_and_propagate(800)
        target = self._amount_finding_key()
        self.assertIsNotNone(target, "expected an amount mismatch from the wrong extraction")

        # Act: correct it to the ledger value 250 (verify-after should pass).
        applied = apply_correction(self.att, target, {"p1": _fields(250)},
                                   evidence="/abs/2099-01/x_p1.png", agent="triage-agent",
                                   target="local", cache_dir=self._cache)
        batch = applied["batch_id"]

        # Assert: applied, data changed, finding cleared, audit row complete.
        self.assertEqual(applied["result"], "applied", applied)
        self.assertAlmostEqual(self._extracted_amount(), 250.0, places=2)
        self.assertIsNone(self._amount_finding_key(), "finding should have cleared")
        row = next(r for r in list_corrections(attachment_ids=[self.att], target="local")
                   if r["field"] == "valor_total")
        self.assertEqual(row["status"], "applied")
        self.assertEqual((row["from_value"], row["to_value"]), (800, 250))
        self.assertEqual(row["evidence"], "/abs/2099-01/x_p1.png")
        self.assertEqual(row["agent"], "triage-agent")
        self.assertEqual(row["page_label"], "p1")
        self.assertEqual(row["target_finding_key"], target)
        self.assertEqual(row["period"], self.period)
        self.assertIsNotNone(row["created_at"])

        # SC-004: the record lives in D1, not the ephemeral cache — survives a full wipe.
        shutil.rmtree(self._cache, ignore_errors=True)
        self._cache = tempfile.mkdtemp()
        self.assertTrue(list_corrections(attachment_ids=[self.att], target="local"))

        # SC-003: undo restores the pre-correction value and the original finding reappears.
        undone = undo_correction(batch, actor="gustavo", target="local", cache_dir=self._cache)
        self.assertEqual(undone["result"], "reverted", undone)
        self.assertAlmostEqual(self._extracted_amount(), 800.0, places=2)
        self.assertIsNotNone(self._amount_finding_key(), "original finding should reappear")
        rows = list_corrections(attachment_ids=[self.att], target="local")
        self.assertTrue(all(r["status"] == "reverted" and r["reverted_by"] == "gustavo"
                            and r["reverted_at"] for r in rows))

        # FR-008: a second undo of the now-reverted batch is rejected, no change.
        self.assertEqual(undo_correction(batch, target="local", cache_dir=self._cache)["result"], "rejected")

    # -- US1: verify-after FAIL -> rollback (SC-002) ----------------------------

    def test_apply_fail_rolls_back_byte_for_byte(self):
        self._stage_and_propagate(800)
        target = self._amount_finding_key()
        before_amount = self._extracted_amount()
        self.assertAlmostEqual(before_amount, 800.0, places=2)

        # A correction that does NOT clear the amount finding (900 still != 250) -> verify FAIL.
        result = apply_correction(self.att, target, {"p1": _fields(900)},
                                  target="local", cache_dir=self._cache)

        self.assertEqual(result["result"], "rolled-back", result)
        # Data restored to the pre-correction extraction (SC-002).
        self.assertAlmostEqual(self._extracted_amount(), 800.0, places=2)
        # The finding is still open (nothing was silently hidden).
        self.assertIsNotNone(self._amount_finding_key())
        rows = list_corrections(attachment_ids=[self.att], status="rolled-back", target="local")
        self.assertTrue(rows)
        self.assertTrue(all(r["status"] == "rolled-back" for r in rows))

    # -- US1: no-op + unverifiable write no row --------------------------------

    def test_no_op_writes_no_row(self):
        # A finding exists (800 != 250). "Correcting" to the SAME current values is a no-op (FR-009):
        # the target IS present (so it passes the fail-closed gate), but the per-field diff is empty.
        self._stage_and_propagate(800)
        target = self._amount_finding_key()
        self.assertIsNotNone(target)
        result = apply_correction(self.att, target, {"p1": _fields(800)},
                                  target="local", cache_dir=self._cache)
        self.assertEqual(result["result"], "no-op", result)
        self.assertEqual(h.count("data_corrections", f"attachment_id = '{self.att}'"), 0)

    def test_unverifiable_writes_no_row(self):
        self._stage_and_propagate(250)  # no finding present
        # Target a finding that does not exist -> fail-closed, never applied (FR-010).
        result = apply_correction(self.att, "no-such-finding|amount|x|y", {"p1": _fields(320)},
                                  target="local", cache_dir=self._cache)
        self.assertEqual(result["result"], "unverifiable", result)
        self.assertEqual(h.count("data_corrections", f"attachment_id = '{self.att}'"), 0)
        # Data unchanged (still 250).
        self.assertAlmostEqual(self._extracted_amount(), 250.0, places=2)


if __name__ == "__main__":
    unittest.main()
