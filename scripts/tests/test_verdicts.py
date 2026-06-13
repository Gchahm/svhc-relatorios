"""Tests for analysis.verdicts loop bookkeeping (TEST-002 / issue #69).

Pure file IO + arithmetic. `loop_state` calls `summarize_mismatches` (which hits D1); we stub
that module-level symbol with `unittest.mock.patch` (stdlib — not a new dependency, and it
*prevents* the D1 call) to feed a fixed mismatch list.
"""

import tempfile
import unittest
from unittest import mock

from analysis import verdicts
from analysis.verdicts import (
    _attachment_ids_of,
    _latest_verdicts,
    _upsert_history,
    _verdict_history_by_key,
    load_verdicts_file,
    loop_state,
    mismatch_key,
    record_verdict,
    save_verdicts_file,
    upsert_verdict,
    validate_fix,
    validate_verdict,
)


class MismatchKeyTest(unittest.TestCase):
    def test_per_attachment(self):
        m = {"period": "2025-12", "kind": "amount", "attachment_id": "a1", "entry_id": "e1"}
        self.assertEqual(mismatch_key(m), "2025-12|amount|a1|e1")

    def test_document_overpayment(self):
        m = {"period": "2025-12", "kind": "document_overpayment", "document_id": "d1"}
        self.assertEqual(mismatch_key(m), "2025-12|document_overpayment|d1")

    def test_attachment_ids_of(self):
        self.assertEqual(_attachment_ids_of({"attachment_id": "a1"}), ["a1"])
        self.assertEqual(
            _attachment_ids_of({"kind": "document_overpayment", "attachment_ids": ["a1", "a2"]}),
            ["a1", "a2"],
        )


class ValidateVerdictTest(unittest.TestCase):
    def test_missing_key(self):
        with self.assertRaises(ValueError):
            validate_verdict({"verdict": "true"})

    def test_invalid_verdict(self):
        with self.assertRaises(ValueError):
            validate_verdict({"mismatch_key": "k", "verdict": "maybe"})

    def test_false_requires_root_cause(self):
        with self.assertRaises(ValueError):
            validate_verdict({"mismatch_key": "k", "verdict": "false"})

    def test_false_with_valid_root_cause(self):
        validate_verdict({
            "mismatch_key": "k",
            "verdict": "false",
            "root_cause": {"area": "reading", "hypothesis": "misread the total"},
        })

    def test_false_bad_area(self):
        with self.assertRaises(ValueError):
            validate_verdict({
                "mismatch_key": "k", "verdict": "false",
                "root_cause": {"area": "nope", "hypothesis": "x"},
            })

    def test_root_cause_forbidden_unless_false(self):
        with self.assertRaises(ValueError):
            validate_verdict({
                "mismatch_key": "k", "verdict": "true",
                "root_cause": {"area": "reading", "hypothesis": "x"},
            })

    def test_invalid_confidence(self):
        with self.assertRaises(ValueError):
            validate_verdict({"mismatch_key": "k", "verdict": "true", "confidence": "huge"})

    def test_true_ok(self):
        validate_verdict({"mismatch_key": "k", "verdict": "true"})


class ValidateFixTest(unittest.TestCase):
    def test_rejects_merged(self):
        with self.assertRaises(ValueError):
            validate_fix({"status": "merged"})

    def test_accepts_pr_open(self):
        validate_fix({"status": "pr-open"})


class UpsertVerdictTest(unittest.TestCase):
    def test_latest_wins_per_key(self):
        data = {"verdicts": []}
        upsert_verdict(data, {"mismatch_key": "k", "verdict": "false",
                              "root_cause": {"area": "reading", "hypothesis": "h"}}, 1)
        upsert_verdict(data, {"mismatch_key": "k", "verdict": "true"}, 2)
        latest = _latest_verdicts(data)
        self.assertEqual(latest["k"]["verdict"], "true")
        self.assertEqual(latest["k"]["iteration"], 2)
        # history retains both verdict values
        self.assertEqual(_verdict_history_by_key(data)["k"], {"false", "true"})

    def test_same_iteration_overwrites(self):
        data = {"verdicts": []}
        upsert_verdict(data, {"mismatch_key": "k", "verdict": "true"}, 1)
        upsert_verdict(data, {"mismatch_key": "k", "verdict": "transient"}, 1)
        self.assertEqual(len(data["verdicts"]), 1)
        self.assertEqual(data["verdicts"][0]["verdict"], "transient")


class UpsertHistoryTest(unittest.TestCase):
    def test_replaces_and_sorts(self):
        h = []
        h = _upsert_history(h, {"iteration": 2, "open_count": 5})
        h = _upsert_history(h, {"iteration": 1, "open_count": 9})
        h = _upsert_history(h, {"iteration": 2, "open_count": 3})  # replace it=2
        self.assertEqual([r["iteration"] for r in h], [1, 2])
        self.assertEqual(h[1]["open_count"], 3)


class FileRoundTripTest(unittest.TestCase):
    def test_load_default_when_absent(self):
        with tempfile.TemporaryDirectory() as d:
            data = load_verdicts_file(d, "2025-12")
            self.assertEqual(data, {"period": "2025-12", "verdicts": [], "loop_state": None})

    def test_save_then_load(self):
        with tempfile.TemporaryDirectory() as d:
            save_verdicts_file(d, "2025-12", {"period": "2025-12", "verdicts": [{"mismatch_key": "k"}], "loop_state": None})
            data = load_verdicts_file(d, "2025-12")
            self.assertEqual(data["verdicts"][0]["mismatch_key"], "k")


class RecordVerdictTest(unittest.TestCase):
    def test_record_and_attach_fix(self):
        with tempfile.TemporaryDirectory() as d:
            record_verdict(d, "2025-12", 1, {"mismatch_key": "k", "verdict": "false",
                                             "root_cause": {"area": "reading", "hypothesis": "h"}})
            data = record_verdict(d, "2025-12", 1, {"mismatch_key": "k"},
                                  fix={"status": "pr-open", "pr_url": "http://x"})
            v = next(v for v in data["verdicts"] if v["mismatch_key"] == "k" and v["iteration"] == 1)
            self.assertEqual(v["fix"]["status"], "pr-open")

    def test_record_requires_key(self):
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(ValueError):
                record_verdict(d, "2025-12", 1, {"verdict": "true"})


def _mm(kind="amount", attachment_id="a1", entry_id="e1", period="2025-12"):
    return {"period": period, "kind": kind, "attachment_id": attachment_id, "entry_id": entry_id}


class LoopStateTest(unittest.TestCase):
    def _run(self, d, mismatches, iteration=None, **kw):
        with mock.patch.object(verdicts, "summarize_mismatches", return_value=mismatches):
            return loop_state("local", "2025-12", cache_dir=d, iteration=iteration, **kw)

    def test_converged_when_no_open(self):
        with tempfile.TemporaryDirectory() as d:
            mm = _mm()
            key = mismatch_key(mm)
            record_verdict(d, "2025-12", 1, {"mismatch_key": key, "verdict": "true"})
            state = self._run(d, [mm], iteration=1)
            self.assertEqual(state["findings"], [key])
            self.assertEqual(state["open"], [])
            self.assertEqual(state["terminate"]["reason"], "converged")

    def test_open_set_and_affected(self):
        with tempfile.TemporaryDirectory() as d:
            mm = _mm()
            state = self._run(d, [mm], iteration=1)  # unreviewed → open
            self.assertEqual(state["open"], [mismatch_key(mm)])
            self.assertEqual(state["affected_attachment_ids"], ["a1"])
            self.assertIsNone(state["terminate"])  # iteration 1 of default max 3

    def test_max_iterations(self):
        with tempfile.TemporaryDirectory() as d:
            mm = _mm()
            state = self._run(d, [mm], iteration=3, max_iterations=3)
            self.assertEqual(state["terminate"]["reason"], "max-iterations")

    def test_no_progress_on_flip(self):
        with tempfile.TemporaryDirectory() as d:
            mm = _mm()
            key = mismatch_key(mm)
            record_verdict(d, "2025-12", 1, {"mismatch_key": key, "verdict": "transient"})
            record_verdict(d, "2025-12", 2, {"mismatch_key": key, "verdict": "false",
                                             "root_cause": {"area": "reading", "hypothesis": "h"}})
            state = self._run(d, [mm], iteration=2)
            self.assertEqual(state["terminate"]["reason"], "no-progress")

    def test_page_error_goes_to_data_quality(self):
        with tempfile.TemporaryDirectory() as d:
            mm = _mm(kind="page-error")
            key = mismatch_key(mm)
            record_verdict(d, "2025-12", 1, {"mismatch_key": key, "verdict": "page-error"})
            state = self._run(d, [mm], iteration=1)
            self.assertEqual(state["data_quality"], [key])
            self.assertEqual(state["terminate"]["reason"], "converged")


if __name__ == "__main__":
    unittest.main()
