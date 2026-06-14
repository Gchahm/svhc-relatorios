"""Unit tests for the data-correction audit trail pure seams (feature 054 / TRIAGE-003).

Covers the pure, D1-free helpers in ``analysis.corrections``: id builders (determinism +
idempotence), the per-field diff, the verify-after rule (incl. fail-closed), the undo status guard,
the row builder's JSON encoding, the list-corrections WHERE/ordering builder, and the structural
independence from the code-fix verdicts store (US3-AC2).

Run: ``python -m unittest discover -s scripts/tests -t scripts``
"""

import json
import unittest
from unittest import mock

from analysis import corrections
from analysis.corrections import (
    STATUS_APPLIED,
    STATUS_FLAGGED,
    STATUS_REVERTED,
    STATUS_ROLLED_BACK,
    batch_id,
    can_undo,
    correction_id,
    correction_row,
    field_diff,
    list_corrections,
    verify_after,
)


def _fields(valor_total=320, **over):
    # A typed NFS-e transcription (EXTRACT-007 typed-only contract). The ``valor_total`` knob sets the
    # nested net (valores.valor_liquido) — the field the nfse mapper reconciles on.
    base = {
        "doc_type": "nfse",
        "schema_version": "1",
        "raw_text": "NFS-e EXEMPLO ...",
        "numero": "123",
        "data_emissao": "2099-01-10",
        "prestador": {"nome": "EXEMPLO LTDA", "cnpj": "11222333000181"},
        "valores": {"valor_servico": valor_total, "deducoes": 0, "valor_liquido": valor_total},
        "discriminacao_servico": "servico",
    }
    base.update(over)
    return base


class IdBuilderTest(unittest.TestCase):
    def test_batch_id_deterministic_and_idempotent(self):
        pages = {"p1": _fields(valor_total=320)}
        a = batch_id("att-1", "k", pages)
        b = batch_id("att-1", "k", pages)
        self.assertEqual(a, b)  # FR-012: identical inputs -> identical id

    def test_batch_id_ignores_dict_order(self):
        # Canonicalization sorts keys, so page-key order does not change the id.
        p1 = {"p1": _fields(), "p2": _fields(valor_total=10)}
        p2 = {"p2": _fields(valor_total=10), "p1": _fields()}
        self.assertEqual(batch_id("att-1", "k", p1), batch_id("att-1", "k", p2))

    def test_batch_id_differs_on_value_change(self):
        self.assertNotEqual(
            batch_id("att-1", "k", {"p1": _fields(valor_total=320)}),
            batch_id("att-1", "k", {"p1": _fields(valor_total=800)}),
        )

    def test_correction_id_per_field(self):
        b = batch_id("att-1", "k", {"p1": _fields()})
        self.assertNotEqual(correction_id(b, "p1", "valor_total"), correction_id(b, "p1", "valor_liquido"))
        self.assertEqual(correction_id(b, "p1", "valor_total"), correction_id(b, "p1", "valor_total"))


class FieldDiffTest(unittest.TestCase):
    # field_diff compares top-level keys generically; for a typed nfse payload the amount lives under
    # the top-level `valores` object, so a changed total surfaces as a changed `valores` field.
    def test_changed_field_only(self):
        cur = _fields(valor_total=800)
        new = _fields(valor_total=320)
        diff = field_diff(cur, new)
        self.assertEqual(
            diff,
            [{
                "field": "valores",
                "from": {"valor_servico": 800, "deducoes": 0, "valor_liquido": 800},
                "to": {"valor_servico": 320, "deducoes": 0, "valor_liquido": 320},
            }],
        )

    def test_no_change_is_empty(self):
        self.assertEqual(field_diff(_fields(), _fields()), [])  # FR-009 no-op

    def test_none_current_is_change_from_null(self):
        diff = field_diff(None, {"valor_total": 320, "cnpj_emitente": "x"})
        self.assertEqual(
            sorted(diff, key=lambda d: d["field"]),
            [{"field": "cnpj_emitente", "from": None, "to": "x"},
             {"field": "valor_total", "from": None, "to": 320}],
        )

    def test_deterministic_field_order(self):
        cur = _fields(numero="1", data_emissao="2099-01-01")
        new = _fields(numero="9", data_emissao="2099-01-02")
        fields = [d["field"] for d in field_diff(cur, new)]
        self.assertEqual(fields, sorted(fields))


class VerifyAfterTest(unittest.TestCase):
    def test_pass_when_cleared_and_no_new(self):
        ok, reason = verify_after({"k", "x"}, {"x"}, "k")
        self.assertTrue(ok)
        self.assertEqual(reason, "")

    def test_fail_when_target_not_cleared(self):
        ok, reason = verify_after({"k"}, {"k"}, "k")
        self.assertFalse(ok)
        self.assertIn("did not clear", reason)

    def test_fail_when_new_finding_appears(self):
        ok, reason = verify_after({"k"}, {"newkind"}, "k")
        self.assertFalse(ok)
        self.assertIn("new finding", reason)

    def test_unverifiable_when_target_absent_before(self):
        # FR-010 fail-closed: target not in BEFORE -> never apply.
        ok, reason = verify_after({"x"}, {"x"}, "k")
        self.assertFalse(ok)
        self.assertIn("unverifiable", reason)


class StatusGuardTest(unittest.TestCase):
    def test_can_undo_only_applied(self):
        self.assertTrue(can_undo(STATUS_APPLIED))
        for s in (STATUS_ROLLED_BACK, STATUS_FLAGGED, STATUS_REVERTED):
            self.assertFalse(can_undo(s), s)  # FR-008


class CorrectionRowTest(unittest.TestCase):
    def test_json_encodes_value_columns(self):
        row = correction_row(
            row_id="r1", batch="b1", attachment_id="att-1", period="2099-01", page_label="p1",
            field="valor_total", from_value=800, to_value=320, evidence="/x/p1.png",
            agent="triage-agent", target_finding_key="k", status=STATUS_APPLIED,
            detail="ok", from_staging=[{"page_label": "p1"}], created_at=123,
        )
        # from/to are JSON-encoded so a number round-trips unambiguously.
        self.assertEqual(json.loads(row["from_value"]), 800)
        self.assertEqual(json.loads(row["to_value"]), 320)
        self.assertEqual(row["status"], STATUS_APPLIED)
        self.assertEqual(row["agent"], "triage-agent")
        self.assertIsNone(row["reverted_at"])
        # from_staging stays a list (d1._escape_sql JSON-serializes it on write).
        self.assertIsInstance(row["from_staging"], list)

    def test_null_value_round_trips(self):
        row = correction_row(
            row_id="r1", batch="b1", attachment_id="att-1", period=None, page_label="p1",
            field="cnpj_emitente", from_value=None, to_value="11222333000181", evidence=None,
            agent="a", target_finding_key=None, status=STATUS_APPLIED, detail=None,
            from_staging=None, created_at=1,
        )
        self.assertIsNone(json.loads(row["from_value"]))


class ListCorrectionsBuilderTest(unittest.TestCase):
    """list_corrections' SQL scoping/ordering, with d1.query stubbed."""

    def test_unscoped_query_has_no_where(self):
        with mock.patch.object(corrections.d1, "query", return_value=[]) as q:
            list_corrections(target="local")
        sql = q.call_args.args[0]
        self.assertNotIn("WHERE", sql)
        self.assertIn("ORDER BY created_at DESC, id", sql)

    def test_scoped_query_ands_filters(self):
        with mock.patch.object(corrections.d1, "query", return_value=[]) as q:
            list_corrections(attachment_ids=["att-1", "att-2"], period="2099-01", status="applied", target="local")
        sql = q.call_args.args[0]
        self.assertIn("attachment_id IN ('att-1','att-2')", sql)
        self.assertIn("period = '2099-01'", sql)
        self.assertIn("status = 'applied'", sql)
        self.assertEqual(sql.count(" AND "), 2)

    def test_decodes_value_columns(self):
        stored = [{"id": "r1", "from_value": json.dumps(800), "to_value": json.dumps(320), "status": "applied"}]
        with mock.patch.object(corrections.d1, "query", return_value=stored):
            rows = list_corrections(target="local")
        self.assertEqual(rows[0]["from_value"], 800)
        self.assertEqual(rows[0]["to_value"], 320)


class IndependenceFromVerdictsTest(unittest.TestCase):
    """US3-AC2: the data-correction store shares no schema/semantics with the code-fix verdicts store."""

    def test_correction_row_has_no_verdict_fields(self):
        row = correction_row(
            row_id="r", batch="b", attachment_id="a", period=None, page_label="p1", field="f",
            from_value=1, to_value=2, evidence=None, agent="a", target_finding_key=None,
            status=STATUS_APPLIED, detail=None, from_staging=None, created_at=1,
        )
        for verdict_field in ("verdict", "mismatch_key", "fix", "root_cause", "iteration"):
            self.assertNotIn(verdict_field, row)

    def test_corrections_module_does_not_call_verdicts_file_api(self):
        # The module never reads/writes the ephemeral <period>.verdicts.json store: it imports only
        # the pure `mismatch_key` identity helper from verdicts, never the file load/save API.
        self.assertFalse(hasattr(corrections, "save_verdicts_file"))
        self.assertFalse(hasattr(corrections, "load_verdicts_file"))
        self.assertFalse(hasattr(corrections, "record_verdict"))
        # The only verdicts symbol it uses is the stable mismatch identity (so it speaks the loop's
        # finding-key language) — not the verdict store.
        self.assertTrue(hasattr(corrections, "mismatch_key"))


class ApplyCorrectionOrchestrationTest(unittest.TestCase):
    """apply_correction's branch logic, with every D1/pipeline seam stubbed (no live D1)."""

    def setUp(self):
        # Patch the D1/pipeline-touching seams; leave the pure logic (diff/verify/ids) real.
        self.patches = {
            "_attachment_context": mock.patch.object(corrections, "_attachment_context", return_value=("2099-01", None)),
            "_affected_scope": mock.patch.object(corrections, "_affected_scope", return_value=["att-1"]),
            "record_classification": mock.patch.object(corrections, "record_classification"),
            "_propagate": mock.patch.object(corrections, "_propagate"),
            "_restore_staging": mock.patch.object(corrections, "_restore_staging", return_value=True),
            "_write_rows": mock.patch.object(corrections, "_write_rows"),
        }
        self.m = {k: p.start() for k, p in self.patches.items()}
        self.addCleanup(lambda: [p.stop() for p in self.patches.values()])

    def _run(self, before, after, *, snapshot=None, pages=None, target_key="k"):
        snapshot = snapshot if snapshot is not None else [
            {"attachment_id": "att-1", "page_label": "p1", "response": _fields(valor_total=800)}
        ]
        pages = pages if pages is not None else {"p1": _fields(valor_total=320)}
        with mock.patch.object(corrections, "_snapshot_staging", return_value=snapshot), \
             mock.patch.object(corrections, "_finding_keys", side_effect=[set(before), set(after)]):
            return corrections.apply_correction("att-1", target_key, pages, target="local")

    def test_applied_when_verify_passes(self):
        res = self._run(before={"k"}, after=set())
        self.assertEqual(res["result"], "applied")
        self.assertTrue(self.m["record_classification"].called)
        self.assertTrue(self.m["_write_rows"].called)
        self.assertFalse(self.m["_restore_staging"].called)

    def test_unverifiable_short_circuits_before_any_write(self):
        res = self._run(before={"other"}, after=set(), target_key="k")
        self.assertEqual(res["result"], "unverifiable")
        self.assertFalse(self.m["record_classification"].called)
        self.assertFalse(self.m["_write_rows"].called)

    def test_no_op_when_diff_empty(self):
        # corrected == current ⇒ empty diff ⇒ no-op, no staging write, no row.
        res = self._run(before={"k"}, after=set(),
                        snapshot=[{"attachment_id": "att-1", "page_label": "p1", "response": _fields(valor_total=320)}])
        self.assertEqual(res["result"], "no-op")
        self.assertFalse(self.m["record_classification"].called)
        self.assertFalse(self.m["_write_rows"].called)

    def test_rolled_back_when_verify_fails_and_restore_ok(self):
        res = self._run(before={"k"}, after={"k"})  # target did not clear
        self.assertEqual(res["result"], "rolled-back")
        self.assertTrue(self.m["_restore_staging"].called)
        self.assertEqual(self.m["_propagate"].call_count, 2)  # apply + re-derive-on-rollback

    def test_flagged_when_restore_fails(self):
        self.m["_restore_staging"].return_value = False
        res = self._run(before={"k"}, after={"newfinding"})  # cleared target but a new finding appeared
        self.assertEqual(res["result"], "flagged")

    def test_rejects_invalid_corrected_page(self):
        with self.assertRaises(ValueError):
            corrections.apply_correction("att-1", "k", {"p1": {"bogus": 1}}, target="local")


class UndoCorrectionOrchestrationTest(unittest.TestCase):
    def test_rejected_when_not_found(self):
        with mock.patch.object(corrections.d1, "query", return_value=[]):
            res = corrections.undo_correction("missing", target="local")
        self.assertEqual(res["result"], "rejected")

    def test_rejected_when_not_applied(self):
        rows = [{"id": "r1", "batch_id": "b1", "attachment_id": "att-1", "period": "2099-01",
                 "status": "reverted", "from_staging": "[]"}]
        with mock.patch.object(corrections.d1, "query", return_value=rows):
            res = corrections.undo_correction("b1", target="local")
        self.assertEqual(res["result"], "rejected")
        self.assertIn("applied", res["reason"])

    def test_reverts_applied_batch(self):
        rows = [{"id": "r1", "batch_id": "b1", "attachment_id": "att-1", "period": "2099-01",
                 "status": "applied", "from_staging": "[]"}]
        with mock.patch.object(corrections.d1, "query", return_value=rows), \
             mock.patch.object(corrections, "_restore_staging", return_value=True) as restore, \
             mock.patch.object(corrections, "_propagate") as prop, \
             mock.patch.object(corrections, "_update_batch_status") as upd:
            res = corrections.undo_correction("b1", actor="gustavo", target="local")
        self.assertEqual(res["result"], "reverted")
        self.assertTrue(restore.called and prop.called)
        self.assertEqual(upd.call_args.kwargs["reverted_by"], "gustavo")

    def test_rejected_when_restore_fails(self):
        rows = [{"id": "r1", "batch_id": "b1", "attachment_id": "att-1", "period": "2099-01",
                 "status": "applied", "from_staging": "[]"}]
        with mock.patch.object(corrections.d1, "query", return_value=rows), \
             mock.patch.object(corrections, "_restore_staging", return_value=False):
            res = corrections.undo_correction("b1", target="local")
        self.assertEqual(res["result"], "rejected")


if __name__ == "__main__":
    unittest.main()
