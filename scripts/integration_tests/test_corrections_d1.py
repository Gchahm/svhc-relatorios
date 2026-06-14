"""Real-D1 integration tests for the data-correction audit trail (feature 054 / TRIAGE-003).

Drive the full ``apply_correction`` / ``list_corrections`` / ``undo_correction`` flow against local
Miniflare D1 (the real ``scripts/common/d1.py`` wrapper, the real staging-driven apply + analyze
pipeline), on the synthetic ``2099-01`` period. Covers:

- US1: a correction whose verify-after PASSES persists the change + an ``applied`` row with all
  required fields; a correction whose verify-after FAILS (target not cleared) rolls the data back
  byte-for-byte (SC-002) and records ``rolled-back``; the no-op + unverifiable (fail-closed) paths
  write no row.
- US2: list returns the recorded fields; undo restores the pre-correction value (SC-003), the
  original finding reappears, and the record becomes ``reverted``; a second undo is rejected (FR-008).
- US3: the record survives an ephemeral-cache wipe and stays listable/undoable (SC-004).

Run: ``pnpm test:py:integration`` (needs ``wrangler`` + an applied local migration set).
"""

from __future__ import annotations

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
        h.restore()
        # E3 is a singleton (no shared-NF sibling), ledger amount 250.00 — a clean correction target.
        self.att = self.ids["attachments"]["E3"]
        self.entry = self.ids["entries"]["E3"]
        self.period = self.ids["period"]
        self._cache = tempfile.mkdtemp()
        # Clean any correction rows a prior test left for this attachment (restore() doesn't touch
        # data_corrections — it is outside the synthetic analysis-owned reset set).
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

    # -- US1: verify-after PASS -------------------------------------------------

    def test_apply_pass_records_and_changes(self):
        # Arrange: a wrong extraction (800) creates an amount mismatch vs the ledger's 250.
        self._stage_and_propagate(800)
        target = self._amount_finding_key()
        self.assertIsNotNone(target, "expected an amount mismatch from the wrong extraction")

        # Act: correct it to the ledger value 250 (verify-after should pass).
        result = apply_correction(self.att, target, {"p1": _fields(250)},
                                  evidence="/abs/2099-01/x_p1.png", agent="triage-agent",
                                  target="local", cache_dir=self._cache)

        # Assert: applied, data changed, finding cleared, audit row complete.
        self.assertEqual(result["result"], "applied", result)
        self.assertAlmostEqual(self._extracted_amount(), 250.0, places=2)
        self.assertIsNone(self._amount_finding_key(), "finding should have cleared")
        rows = list_corrections(attachment_ids=[self.att], target="local")
        self.assertTrue(rows)
        row = next(r for r in rows if r["field"] == "valor_total")
        self.assertEqual(row["status"], "applied")
        self.assertEqual(row["from_value"], 800)
        self.assertEqual(row["to_value"], 250)
        self.assertEqual(row["evidence"], "/abs/2099-01/x_p1.png")
        self.assertEqual(row["agent"], "triage-agent")
        self.assertEqual(row["page_label"], "p1")
        self.assertEqual(row["target_finding_key"], target)
        self.assertEqual(row["period"], self.period)
        self.assertIsNotNone(row["created_at"])

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

    # -- US2: list + undo (SC-003, FR-008) -------------------------------------

    def test_undo_restores_and_records(self):
        self._stage_and_propagate(800)
        target = self._amount_finding_key()
        applied = apply_correction(self.att, target, {"p1": _fields(250)}, target="local", cache_dir=self._cache)
        self.assertEqual(applied["result"], "applied")
        batch = applied["batch_id"]
        self.assertAlmostEqual(self._extracted_amount(), 250.0, places=2)

        # Undo restores the pre-correction value (SC-003) and the original finding reappears.
        undone = undo_correction(batch, actor="gustavo", target="local", cache_dir=self._cache)
        self.assertEqual(undone["result"], "reverted", undone)
        self.assertAlmostEqual(self._extracted_amount(), 800.0, places=2)
        self.assertIsNotNone(self._amount_finding_key(), "original finding should reappear")
        rows = list_corrections(attachment_ids=[self.att], target="local")
        self.assertTrue(all(r["status"] == "reverted" for r in rows))
        self.assertTrue(all(r["reverted_by"] == "gustavo" for r in rows))
        self.assertTrue(all(r["reverted_at"] for r in rows))

    def test_second_undo_rejected(self):
        self._stage_and_propagate(800)
        target = self._amount_finding_key()
        batch = apply_correction(self.att, target, {"p1": _fields(250)}, target="local", cache_dir=self._cache)["batch_id"]
        self.assertEqual(undo_correction(batch, target="local", cache_dir=self._cache)["result"], "reverted")
        # Second undo of a now-reverted batch is rejected, no change (FR-008).
        second = undo_correction(batch, target="local", cache_dir=self._cache)
        self.assertEqual(second["result"], "rejected", second)

    # -- US3: durability across a cache wipe (SC-004) --------------------------

    def test_record_survives_cache_wipe(self):
        import shutil

        self._stage_and_propagate(800)
        target = self._amount_finding_key()
        batch = apply_correction(self.att, target, {"p1": _fields(250)}, target="local", cache_dir=self._cache)["batch_id"]
        # Wipe the ephemeral cache entirely.
        shutil.rmtree(self._cache, ignore_errors=True)
        self._cache = tempfile.mkdtemp()
        # The correction is still listable (it lives in D1, not the cache).
        rows = list_corrections(attachment_ids=[self.att], target="local")
        self.assertTrue(rows)
        # And still undoable.
        self.assertEqual(undo_correction(batch, target="local", cache_dir=self._cache)["result"], "reverted")


if __name__ == "__main__":
    unittest.main()
