"""Unit tests for the re-derive pure seams (feature 056 / EXTRACT-005).

Covers the D1-free seams: the record→staging reconstruction transform
(``page_classifications.staging_rows_from_records``) and the scope/skip/no-op logic of
``extractions.re_derive`` with all D1 + apply/analyze boundaries mocked. No D1/R2/network.

Run: ``python -m unittest discover -s scripts/tests -t scripts``
"""

import unittest
from unittest import mock

from analysis import extractions
from analysis.page_classifications import page_classification_id, staging_rows_from_records

from tests._fixtures import attachment, make_period, make_refs


# --------------------------------------------------------------------------- #
# staging_rows_from_records — the pure record→staging transform
# --------------------------------------------------------------------------- #
class StagingRowsFromRecordsTest(unittest.TestCase):
    def test_typed_dict_response_decoded_with_correct_id(self):
        rec = {"page_label": "p1", "page_index": 0, "response": {"doc_type": "nfse", "x": 1}, "parse_error": None}
        rows = staging_rows_from_records("att-1", [rec])
        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertEqual(row["id"], page_classification_id("att-1", "p1"))
        self.assertEqual(row["attachment_id"], "att-1")
        self.assertEqual(row["page_label"], "p1")
        self.assertEqual(row["page_index"], 0)
        self.assertEqual(row["response"], {"doc_type": "nfse", "x": 1})
        self.assertIsNone(row["error"])
        self.assertIn("recorded_at", row)

    def test_json_string_response_is_decoded(self):
        rec = {"page_label": "p2", "page_index": 1, "response": '{"doc_type": "danfe"}', "parse_error": None}
        rows = staging_rows_from_records("att-1", [rec])
        self.assertEqual(rows[0]["response"], {"doc_type": "danfe"})

    def test_unparseable_json_string_becomes_none(self):
        rec = {"page_label": "p1", "page_index": 0, "response": "not json", "parse_error": None}
        rows = staging_rows_from_records("att-1", [rec])
        self.assertIsNone(rows[0]["response"])

    def test_parse_error_record_maps_to_error_and_null_response(self):
        rec = {"page_label": "p1", "page_index": 0, "response": None, "parse_error": "image unreadable"}
        rows = staging_rows_from_records("att-1", [rec])
        self.assertIsNone(rows[0]["response"])
        self.assertEqual(rows[0]["error"], "image unreadable")

    def test_row_without_page_label_is_skipped(self):
        rec = {"page_label": None, "page_index": 0, "response": {"doc_type": "nfse"}, "parse_error": None}
        self.assertEqual(staging_rows_from_records("att-1", [rec]), [])

    def test_empty_input(self):
        self.assertEqual(staging_rows_from_records("att-1", []), [])
        self.assertEqual(staging_rows_from_records("att-1", None), [])


# --------------------------------------------------------------------------- #
# _redrive_scope — candidate selection + shared-NF group expansion (pure)
# --------------------------------------------------------------------------- #
class RedriveScopeTest(unittest.TestCase):
    def _periods(self):
        # Two attachments share one NF (same content_hash) → one group; a3 is its own group.
        atts = [
            attachment("a1", "e1", file_path="p/a1_p1.png", content_hash="H", classified_at=1),
            attachment("a2", "e2", file_path="p/a2_p1.png", content_hash="H", classified_at=1),
            attachment("a3", "e3", file_path="p/a3_p1.png", content_hash="K", classified_at=1),
        ]
        pd = make_period(
            "2099-01",
            attachments=atts,
            raw_extra={"attachment_analyses": [{"attachment_id": "a1"}, {"attachment_id": "a2"}, {"attachment_id": "a3"}]},
        )
        return {"2099-01": pd}

    def test_global_scope_is_all_classified(self):
        scope = extractions._redrive_scope(self._periods(), None)
        self.assertEqual(scope, {"2099-01": {"a1", "a2", "a3"}})

    def test_attachment_scope_expands_to_full_group(self):
        # Selecting only a1 must pull in its sibling a2 (shared NF), but not a3.
        scope = extractions._redrive_scope(self._periods(), ["a1"])
        self.assertEqual(scope, {"2099-01": {"a1", "a2"}})

    def test_attachment_scope_singleton_group(self):
        scope = extractions._redrive_scope(self._periods(), ["a3"])
        self.assertEqual(scope, {"2099-01": {"a3"}})

    def test_period_with_no_classified_is_omitted(self):
        pd = make_period("2099-02", attachments=[attachment("z", "e", classified_at=1)], raw_extra={"attachment_analyses": []})
        scope = extractions._redrive_scope({"2099-02": pd}, None)
        self.assertEqual(scope, {})

    def test_unknown_attachment_id_yields_empty_scope(self):
        scope = extractions._redrive_scope(self._periods(), ["nope"])
        self.assertEqual(scope, {})


# --------------------------------------------------------------------------- #
# re_derive — orchestration: skip-no-transcription, no-op short-circuit, summary
# --------------------------------------------------------------------------- #
class ReDeriveOrchestrationTest(unittest.TestCase):
    def _one_attachment_period(self):
        pd = make_period(
            "2099-01",
            attachments=[attachment("a1", "e1", file_path="p/a1_p1.png", content_hash="H", classified_at=1)],
            raw_extra={"attachment_analyses": [{"attachment_id": "a1"}]},
        )
        return {"2099-01": pd}

    def test_skips_attachment_with_no_parseable_transcription(self):
        # Stored records carry only a parse_error → no staged response → must NOT be applied.
        records = [{"page_label": "p1", "page_index": 0, "response": None, "parse_error": "bad"}]
        with mock.patch.object(extractions, "load_all_periods", return_value=(self._one_attachment_period(), make_refs())), \
             mock.patch.object(extractions, "load_stored_records", return_value=records), \
             mock.patch.object(extractions.d1, "upsert_tables") as upsert, \
             mock.patch.object(extractions, "clear_classified_stamp") as clear, \
             mock.patch.object(extractions, "apply_extractions") as apply, \
             mock.patch("analysis.run_analysis") as analyze:
            result = extractions.re_derive(target="local")
        self.assertEqual(result["re_derived"], 0)
        self.assertEqual(result["skipped_no_transcription"], 1)
        self.assertEqual(result["periods"], [])
        upsert.assert_not_called()
        clear.assert_not_called()
        apply.assert_not_called()
        analyze.assert_not_called()

    def test_no_op_short_circuits_apply_and_analyze(self):
        # No classified attachments anywhere → nothing staged, no apply/analyze.
        empty = make_period("2099-01", attachments=[], raw_extra={"attachment_analyses": []})
        with mock.patch.object(extractions, "load_all_periods", return_value=({"2099-01": empty}, make_refs())), \
             mock.patch.object(extractions, "apply_extractions") as apply, \
             mock.patch("analysis.run_analysis") as analyze:
            result = extractions.re_derive(target="local")
        self.assertEqual(result, {"re_derived": 0, "skipped_no_transcription": 0, "periods": [], "remote": False})
        apply.assert_not_called()
        analyze.assert_not_called()

    def test_re_derives_and_runs_apply_then_analyze(self):
        records = [{"page_label": "p1", "page_index": 0, "response": {"doc_type": "nfse", "valores": {}}, "parse_error": None}]
        with mock.patch.object(extractions, "load_all_periods", return_value=(self._one_attachment_period(), make_refs())), \
             mock.patch.object(extractions, "load_stored_records", return_value=records), \
             mock.patch.object(extractions.d1, "upsert_tables") as upsert, \
             mock.patch.object(extractions, "clear_classified_stamp") as clear, \
             mock.patch.object(extractions, "apply_extractions") as apply, \
             mock.patch("analysis.run_analysis") as analyze:
            result = extractions.re_derive(target="local")
        self.assertEqual(result["re_derived"], 1)
        self.assertEqual(result["skipped_no_transcription"], 0)
        self.assertEqual(result["periods"], ["2099-01"])
        upsert.assert_called_once()
        clear.assert_called_once_with("a1", "local")
        apply.assert_called_once()
        analyze.assert_called_once()
        # apply + analyze are scoped to the affected period(s).
        self.assertEqual(apply.call_args.kwargs["periods_filter"], ["2099-01"])
        self.assertEqual(analyze.call_args.kwargs["periods_filter"], ["2099-01"])

    def test_remote_flag_in_summary(self):
        empty = make_period("2099-01", attachments=[], raw_extra={"attachment_analyses": []})
        with mock.patch.object(extractions, "load_all_periods", return_value=({"2099-01": empty}, make_refs())):
            result = extractions.re_derive(target="remote")
        self.assertTrue(result["remote"])

    def test_no_periods_returns_zeros(self):
        with mock.patch.object(extractions, "load_all_periods", return_value=({}, make_refs())):
            result = extractions.re_derive(target="local")
        self.assertEqual(result, {"re_derived": 0, "skipped_no_transcription": 0, "periods": [], "remote": False})


if __name__ == "__main__":
    unittest.main()
