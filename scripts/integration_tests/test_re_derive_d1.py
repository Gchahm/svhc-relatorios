"""Feature 056 / EXTRACT-005: ``re-derive`` against real D1.

Exercises the image-free systematic re-run of the deterministic mappers over the STORED
transcriptions (``attachment_analysis_records.response``), against the feature-046 synthetic seed
(local Miniflare D1). Asserts the spec's success criteria, scoping assertions kept to the synthetic
``2099-01`` ids (project memory: never whole-table counts on shared local D1).

Subjects: E3 (seeded classified singleton, NF-1002) and E1/E2 (a shared-NF pair). We classify a
subject through the REAL path first (``record_classification`` → ``apply_extractions``) so the
baseline ``attachment_analyses`` is apply-produced (not the hand-written seed values), then assert
``re_derive`` reproduces it from the durable per-page records.
"""

from __future__ import annotations

import unittest

from analysis.extractions import apply_extractions, mark_pending, re_derive
from analysis.page_classifications import record_classification

from . import _harness as h


def _flat(*, numero_documento="NF-1002", valor_total=250.00) -> dict:
    """A valid typed EXTRACT-001 danfe per-page transcription (EXTRACT-007 typed-only contract).

    Knob names (``numero_documento``/``valor_total``) are kept for the existing call sites; they map
    onto the typed danfe ``numero`` / ``totais.valor_total_nota``.
    """
    return {
        "doc_type": "danfe",
        "schema_version": "1",
        "raw_text": f"DANFE {numero_documento} EXEMPLO",
        "numero": numero_documento,
        "data_emissao": "05/01/2099",
        "emitente": {"nome": "EXEMPLO Fornecedor B", "cnpj": "11222333000181"},
        "totais": {"valor_total_nota": valor_total},
    }


def _analysis_no_ts(attachment_id: str) -> dict | None:
    """The attachment's ``attachment_analyses`` row with the volatile ``analyzed_at`` dropped."""
    rows = h.q(f"SELECT * FROM attachment_analyses WHERE attachment_id = '{attachment_id}'")
    if not rows:
        return None
    row = dict(rows[0])
    row.pop("analyzed_at", None)
    return row


class TestReDeriveD1(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        h.seed_once()
        cls.ids = h.ids()
        cls.period = cls.ids["period"]
        cls.e3_att = cls.ids["attachments"]["E3"]
        cls.e1_att = cls.ids["attachments"]["E1"]
        cls.e2_att = cls.ids["attachments"]["E2"]

    maxDiff = None

    def setUp(self):
        # RETAIN the per-test h.restore() here (unlike the sibling TEST-006 trims on reclassify /
        # typed-record): this module is NOT subject-singleton/subject-scoped. test_scoped_run_leaves_
        # out_of_scope_untouched reads E1 (out of scope) as a baseline, and test_shared_nf_group_re_
        # derives_together mutates the E1/E2 shared-NF pair to 300. Without a per-test clean baseline,
        # the order tests run in would let one test's E1/E2/E3 mutation leak into another's "before"
        # snapshot. The five tests each exercise a DISTINCT path, so none can be merged away either —
        # this module's share of the speedup comes from the npx-wrangler removal, not a reseed cut.
        h.restore()

    def _classify_e3(self) -> dict:
        """Classify E3 through the real path; return its apply-produced analysis (no timestamp).

        E3 is seeded already-classified, so first ``mark_pending`` (clears the stamp + any staging),
        then record a fresh staging row, then apply — so the baseline analysis is produced from THIS
        record (and that record is what re-derive later reads back from ``…_records.response``)."""
        mark_pending("local", attachment_ids=[self.e3_att])
        record_classification(self.e3_att, "p1", _flat(), target="local")
        apply_extractions("local", [self.period])
        baseline = _analysis_no_ts(self.e3_att)
        self.assertIsNotNone(baseline)
        return baseline

    def test_reproduce_and_idempotent(self):
        # SC-002: re-derive reproduces the apply-produced analysis from the stored record, and is
        # idempotent across repeated runs (mappers unchanged).
        baseline = self._classify_e3()

        result = re_derive(target="local", periods_filter=[self.period], attachment_ids=[self.e3_att])
        self.assertEqual(result["re_derived"], 1)
        self.assertEqual(result["skipped_no_transcription"], 0)
        self.assertEqual(result["periods"], [self.period])
        self.assertEqual(_analysis_no_ts(self.e3_att), baseline)

        # Second run: still identical (idempotent).
        re_derive(target="local", periods_filter=[self.period], attachment_ids=[self.e3_att])
        self.assertEqual(_analysis_no_ts(self.e3_att), baseline)

    def test_scoped_run_leaves_out_of_scope_untouched(self):
        # SC-003: re-deriving only E3 must not change E1's analysis row.
        self._classify_e3()
        e1_before = _analysis_no_ts(self.e1_att)
        self.assertIsNotNone(e1_before)

        re_derive(target="local", periods_filter=[self.period], attachment_ids=[self.e3_att])

        self.assertEqual(_analysis_no_ts(self.e1_att), e1_before)

    def test_safe_skip_when_no_parseable_transcription(self):
        # SC-004: an attachment whose stored record carries no parseable response is left untouched.
        # Record an ERROR result for E3 (no fields), apply it, then re-derive.
        mark_pending("local", attachment_ids=[self.e3_att])
        record_classification(self.e3_att, "p1", {"error": "page unreadable"}, target="local")
        apply_extractions("local", [self.period])
        before = _analysis_no_ts(self.e3_att)
        self.assertIsNotNone(before)  # apply still wrote an (error) analysis row

        result = re_derive(target="local", periods_filter=[self.period], attachment_ids=[self.e3_att])

        self.assertEqual(result["re_derived"], 0)
        self.assertEqual(result["skipped_no_transcription"], 1)
        self.assertEqual(_analysis_no_ts(self.e3_att), before)  # untouched

    def test_no_mirror_table_writes(self):
        # SC-005: re-derive writes no rows to the scraper-owned mirror tables.
        self._classify_e3()
        ent_before = h.q(f"SELECT * FROM entries WHERE id = '{self.ids['entries']['E3']}'")
        att_before = h.q(f"SELECT * FROM attachments WHERE id = '{self.e3_att}'")

        re_derive(target="local", periods_filter=[self.period])

        self.assertEqual(h.q(f"SELECT * FROM entries WHERE id = '{self.ids['entries']['E3']}'"), ent_before)
        self.assertEqual(h.q(f"SELECT * FROM attachments WHERE id = '{self.e3_att}'"), att_before)

    def test_shared_nf_group_re_derives_together(self):
        # FR-006: selecting one sibling of a shared NF re-derives the whole group. E1+E2 share NF-1001.
        # Classify the group via E1's representative (record both members' staging then apply is the
        # normal flow; here we classify E1 and E2 each so both carry stored records), then re-derive
        # by selecting only E1 and assert E2's analysis is also rebuilt (present + no error).
        mark_pending("local", attachment_ids=[self.e1_att, self.e2_att])
        record_classification(self.e1_att, "p1", _flat(numero_documento="NF-1001", valor_total=300.00), target="local")
        record_classification(self.e2_att, "p1", _flat(numero_documento="NF-1001", valor_total=300.00), target="local")
        apply_extractions("local", [self.period])
        e2_before = _analysis_no_ts(self.e2_att)
        self.assertIsNotNone(e2_before)

        result = re_derive(target="local", periods_filter=[self.period], attachment_ids=[self.e1_att])

        # Both members were in scope (group expansion), and E2's row is reproduced byte-for-byte.
        self.assertGreaterEqual(result["re_derived"], 2)
        self.assertEqual(_analysis_no_ts(self.e2_att), e2_before)


if __name__ == "__main__":
    unittest.main()
