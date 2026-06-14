"""Unit tests for the headless ``classify`` loop + the typed-only gate (EXTRACT-007 / feature 066).

Drives ``analysis.classify.classify_period`` with all I/O mocked: ``load_all_periods`` and
``materialize_period_images`` are patched (no D1/R2), ``record_classification`` is patched (no write),
and a FAKE ``transcribe_page`` callable is injected (no subprocess / no model). Also exercises the
tightened ``validate_page_fields`` gate (flat rejected, typed accepted, error accepted) with a fake
typed validator. Stdlib only.

Run: ``python -m unittest discover -s scripts/tests -t scripts``
"""

import unittest
from unittest import mock

from analysis import classify as classify_mod
from analysis.classify import ClassifyConfigError, _fields_or_error, classify_period
from analysis.page_classifications import validate_page_fields

from tests._fixtures import attachment, entry, make_period, make_refs


def _typed(valor=100.0):
    return {
        "doc_type": "danfe",
        "schema_version": "1",
        "raw_text": "DANFE ...",
        "numero": "NF-1",
        "totais": {"valor_total_nota": valor},
    }


def _periods_with(n_pages_per_attachment, *, recorded_keys=None):
    """One period, one entry+attachment whose file_path lists ``n`` pages; all pending.

    ``recorded_keys`` is the set of (attachment_id, page_label) already in the staging table (so the
    plan's ``recorded`` flag is True for them). Returns ``(periods_dict, refs)``.
    """
    tokens = ";".join(f"2025-12/x_p{i + 1}.png" for i in range(n_pages_per_attachment))
    e = entry("e1", amount=100.0)
    a = attachment("a1", "e1", file_path=tokens, content_hash="h1")
    pcs = []
    for aid, label in recorded_keys or []:
        pcs.append({"attachment_id": aid, "page_label": label, "response": {"doc_type": "danfe"}, "error": None})
    pd = make_period("2025-12", entries=[e], attachments=[a], raw_extra={"page_classifications": pcs})
    return {"2025-12": pd}, make_refs()


def _patch_io(periods, refs):
    """Patch the classify module's loader + materialize so no real I/O runs."""
    return (
        mock.patch.object(classify_mod, "load_all_periods", return_value=(periods, refs)),
        mock.patch.object(classify_mod, "materialize_period_images", return_value=None),
    )


class ClassifyHappyPathTest(unittest.TestCase):
    def test_records_typed_row_per_pending_page(self):
        periods, refs = _periods_with(2)
        load, mat = _patch_io(periods, refs)
        with load, mat, mock.patch.object(classify_mod, "record_classification") as rec:
            result = classify_period(
                "local", ["2025-12"],
                transcribe_page=lambda rp: _typed(),
                typed_validator=lambda payload, dt: [],
            )
        self.assertEqual(result["recorded"], 2)
        self.assertEqual(result["errors"], 0)
        self.assertEqual(result["skipped"], 0)
        self.assertEqual(rec.call_count, 2)
        # Each call records a typed payload for attachment a1 with a page label.
        for c in rec.call_args_list:
            self.assertEqual(c.args[0], "a1")
            self.assertIn(c.args[1], {"p1", "p2"})
            self.assertEqual(c.args[2]["doc_type"], "danfe")

    def test_skips_already_recorded_pages(self):
        periods, refs = _periods_with(2, recorded_keys={("a1", "p1")})
        load, mat = _patch_io(periods, refs)
        with load, mat, mock.patch.object(classify_mod, "record_classification") as rec:
            result = classify_period(
                "local", ["2025-12"],
                transcribe_page=lambda rp: _typed(),
                typed_validator=lambda payload, dt: [],
            )
        # p1 is already recorded -> skipped; only p2 is transcribed.
        self.assertEqual(result["recorded"], 1)
        self.assertEqual(result["skipped"], 1)
        self.assertEqual(rec.call_count, 1)
        self.assertEqual(rec.call_args.args[1], "p2")

    def test_min_amount_filters_out_below_threshold(self):
        periods, refs = _periods_with(1)  # entry amount 100
        load, mat = _patch_io(periods, refs)
        with load, mat, mock.patch.object(classify_mod, "record_classification") as rec:
            result = classify_period(
                "local", ["2025-12"], min_amount=500.0,
                transcribe_page=lambda rp: _typed(),
                typed_validator=lambda payload, dt: [],
            )
        self.assertEqual(result["recorded"], 0)
        rec.assert_not_called()

    def test_no_periods_is_clean_noop(self):
        with mock.patch.object(classify_mod, "load_all_periods", return_value=({}, make_refs())), \
                mock.patch.object(classify_mod, "record_classification") as rec:
            result = classify_period("local", ["2099-99"], transcribe_page=lambda rp: _typed())
        self.assertEqual(result, {"recorded": 0, "errors": 0, "skipped": 0, "periods": [], "remote": False})
        rec.assert_not_called()


class ClassifyErrorHandlingTest(unittest.TestCase):
    def test_per_page_failure_records_error_row_and_continues(self):
        periods, refs = _periods_with(2)
        load, mat = _patch_io(periods, refs)
        calls = {"n": 0}

        def fake(rp):
            calls["n"] += 1
            # First page fails (error sentinel), second succeeds.
            return {"error": "transcription failed: illegible"} if calls["n"] == 1 else _typed()

        with load, mat, mock.patch.object(classify_mod, "record_classification") as rec:
            result = classify_period(
                "local", ["2025-12"], transcribe_page=fake, typed_validator=lambda payload, dt: []
            )
        self.assertEqual(result["recorded"], 1)
        self.assertEqual(result["errors"], 1)
        # Both pages were visited and a row recorded for each (one error, one typed).
        self.assertEqual(rec.call_count, 2)
        recorded_payloads = [c.args[2] for c in rec.call_args_list]
        self.assertIn({"error": "transcription failed: illegible"}, recorded_payloads)

    def test_config_error_stops_the_run(self):
        periods, refs = _periods_with(2)
        load, mat = _patch_io(periods, refs)

        def fake(rp):
            raise ClassifyConfigError("claude: command not found")

        with load, mat, mock.patch.object(classify_mod, "record_classification") as rec:
            with self.assertRaises(ClassifyConfigError):
                classify_period("local", ["2025-12"], transcribe_page=fake, typed_validator=lambda payload, dt: [])
        # The run stopped on the first page — nothing recorded past the failure (FR-006).
        rec.assert_not_called()


class FieldsOrErrorTest(unittest.TestCase):
    def test_parse_errors_become_error_sentinel(self):
        out = _fields_or_error({"doc_type": "danfe", "fields": {"doc_type": "danfe"}, "parse_errors": ["bad json"]})
        self.assertIn("error", out)
        self.assertIn("bad json", out["error"])

    def test_missing_fields_become_error_sentinel(self):
        self.assertIn("error", _fields_or_error({"doc_type": "danfe"}))
        self.assertIn("error", _fields_or_error({"doc_type": "danfe", "fields": {}}))

    def test_clean_envelope_returns_fields(self):
        fields = {"doc_type": "danfe", "schema_version": "1", "totais": {"valor_total_nota": 10}}
        out = _fields_or_error({"doc_type": "danfe", "schema_version": "1", "fields": fields})
        self.assertEqual(out, fields)


class TypedOnlyGateTest(unittest.TestCase):
    """The tightened record-classification gate (EXTRACT-007 / FR-008)."""

    def _fake_validator(self, payload, doc_type):
        return ["$: bad"] if payload.get("bad") else []

    def test_flat_payload_rejected(self):
        flat = {"papel_artefato": "invoice", "valor_total": 100, "cnpj_emitente": "x"}
        err = validate_page_fields(flat, typed_validator=self._fake_validator)
        self.assertIsNotNone(err)
        self.assertIn("doc_type", err)

    def test_typed_payload_accepted(self):
        self.assertIsNone(validate_page_fields(_typed(), typed_validator=self._fake_validator))

    def test_typed_payload_failing_schema_rejected(self):
        err = validate_page_fields({"doc_type": "danfe", "bad": 1}, typed_validator=self._fake_validator)
        self.assertIsNotNone(err)
        self.assertIn("EXTRACT-001 schema", err)

    def test_error_result_accepted(self):
        self.assertIsNone(validate_page_fields({"error": "page illegible"}, typed_validator=self._fake_validator))

    def test_error_result_must_be_exact(self):
        self.assertIsNotNone(validate_page_fields({"error": "x", "extra": 1}, typed_validator=self._fake_validator))

    def test_non_dict_rejected(self):
        self.assertIsNotNone(validate_page_fields([1, 2], typed_validator=self._fake_validator))


if __name__ == "__main__":
    unittest.main()
