"""Unit tests for the composite ``reclassify`` helper (feature 058 / TRIAGE-004, design §4.5).

Covers the pure orchestration seam of ``analysis.corrections.reclassify`` with all D1 / propagation
side effects mocked: empty-pages no-op, validate-before-record (a rejection writes nothing), the
record→propagate ordering with the resolved period, and the unknown-attachment error.

Run: ``python -m unittest discover -s scripts/tests -t scripts``
"""

import unittest
from unittest import mock

from analysis import corrections
from analysis.corrections import reclassify


def _fields(valor_total=320, **over):
    # A typed NFS-e transcription (EXTRACT-007 typed-only contract). The reconciliation total is the
    # net (valores.valor_liquido); ``valor_total`` is the test knob mapped onto it.
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


class ReclassifyTest(unittest.TestCase):
    def test_empty_pages_is_no_op_no_side_effects(self):
        with mock.patch.object(corrections, "record_classification") as rec, mock.patch.object(
            corrections, "_propagate"
        ) as prop, mock.patch.object(corrections, "_attachment_context") as ctx:
            result = reclassify("att-1", {}, target="local")
        self.assertEqual(result["result"], "no-op")
        self.assertEqual(result["pages"], [])
        self.assertFalse(result["remote"])
        rec.assert_not_called()
        prop.assert_not_called()
        ctx.assert_not_called()  # short-circuits before resolving the period

    def test_unknown_attachment_raises_and_records_nothing(self):
        with mock.patch.object(corrections, "_attachment_context", return_value=(None, None)), mock.patch.object(
            corrections, "record_classification"
        ) as rec, mock.patch.object(corrections, "_propagate") as prop:
            with self.assertRaises(ValueError):
                reclassify("missing", {"p1": _fields()}, target="local")
        rec.assert_not_called()
        prop.assert_not_called()

    def test_invalid_page_rejects_before_recording_anything(self):
        # validate_page_fields returns an error string for p2 -> the whole call must write nothing,
        # even though p1 is valid (validate ALL before recording ANY).
        def fake_validate(fields, *, typed_validator=None):
            return None if fields.get("valores", {}).get("valor_liquido") == 320 else "bad"

        pages = {"p1": _fields(valor_total=320), "p2": _fields(valor_total=999)}
        with mock.patch.object(corrections, "_attachment_context", return_value=("2099-01", "h")), mock.patch.object(
            corrections, "validate_page_fields", side_effect=fake_validate
        ), mock.patch.object(corrections, "record_classification") as rec, mock.patch.object(
            corrections, "_propagate"
        ) as prop:
            with self.assertRaises(ValueError):
                reclassify("att-1", pages, target="local")
        rec.assert_not_called()
        prop.assert_not_called()

    def test_valid_pages_record_then_propagate_once_with_period(self):
        pages = {"p1": _fields(), "p2": _fields(valor_total=10, valor_liquido=10, valor_pago=10)}
        with mock.patch.object(corrections, "_attachment_context", return_value=("2099-01", "h")), mock.patch.object(
            corrections, "validate_page_fields", return_value=None
        ), mock.patch.object(corrections, "record_classification") as rec, mock.patch.object(
            corrections, "_propagate"
        ) as prop:
            result = reclassify("att-1", pages, target="local", cache_dir="/tmp/cache")

        self.assertEqual(result["result"], "reclassified")
        self.assertEqual(result["attachment_id"], "att-1")
        self.assertEqual(result["period"], "2099-01")
        self.assertEqual(sorted(result["pages"]), ["p1", "p2"])
        self.assertFalse(result["remote"])
        # One record_classification per page, with the right attachment id + page labels.
        self.assertEqual(rec.call_count, 2)
        recorded_pages = sorted(c.args[1] for c in rec.call_args_list)
        self.assertEqual(recorded_pages, ["p1", "p2"])
        for c in rec.call_args_list:
            self.assertEqual(c.args[0], "att-1")
        # Propagate exactly once, scoped to the resolved period + cache dir.
        prop.assert_called_once_with("att-1", "2099-01", "local", "/tmp/cache")

    def test_remote_flag_reflected_in_result_and_threaded(self):
        with mock.patch.object(corrections, "_attachment_context", return_value=("2099-01", "h")), mock.patch.object(
            corrections, "validate_page_fields", return_value=None
        ), mock.patch.object(corrections, "record_classification") as rec, mock.patch.object(
            corrections, "_propagate"
        ) as prop:
            result = reclassify("att-1", {"p1": _fields()}, target="remote")
        self.assertTrue(result["remote"])
        # target threaded to record_classification (kwarg) + _propagate (positional).
        self.assertEqual(rec.call_args.kwargs.get("target"), "remote")
        self.assertEqual(prop.call_args.args[2], "remote")


if __name__ == "__main__":
    unittest.main()
