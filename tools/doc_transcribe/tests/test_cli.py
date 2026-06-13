"""CLI tests for `python -m doc_transcribe` (EXTRACT-002, US3) — backend injected, no subprocess/network."""

from __future__ import annotations

import io
import json
import os
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout

from doc_transcribe.__main__ import main
from doc_transcribe.tests._helpers import SAMPLE_PNG, FakeBackend, load_example


class CliTest(unittest.TestCase):
    def setUp(self):
        fd, self.image_path = tempfile.mkstemp(suffix=".png")
        with os.fdopen(fd, "wb") as fh:
            fh.write(SAMPLE_PNG)
        self.addCleanup(lambda: os.path.exists(self.image_path) and os.unlink(self.image_path))

    def test_prints_typed_json_exit_zero(self):
        backend = FakeBackend(json.dumps(load_example("recibo")))
        out = io.StringIO()
        with redirect_stdout(out):
            rc = main(["--image", self.image_path, "--type", "recibo"], backend_impl=backend)
        self.assertEqual(rc, 0)
        parsed = json.loads(out.getvalue())
        self.assertEqual(parsed["doc_type"], "recibo")
        self.assertNotIn("parse_errors", parsed)

    def test_bad_model_response_still_exits_zero_with_parse_errors(self):
        backend = FakeBackend("garbage, not json")
        out = io.StringIO()
        with redirect_stdout(out):
            rc = main(["--image", self.image_path], backend_impl=backend)
        self.assertEqual(rc, 0)
        parsed = json.loads(out.getvalue())
        self.assertIn("parse_errors", parsed)
        self.assertEqual(parsed["doc_type"], "outro")

    def test_missing_image_exits_nonzero(self):
        err = io.StringIO()
        with redirect_stderr(err):
            rc = main(["--image", "/no/such/file.png"], backend_impl=FakeBackend("{}"))
        self.assertNotEqual(rc, 0)
        self.assertIn("error", err.getvalue().lower())

    def test_unknown_backend_exits_nonzero(self):
        # argparse choices reject an unknown --backend with SystemExit(2).
        with self.assertRaises(SystemExit):
            main(["--image", self.image_path, "--backend", "nope"])


if __name__ == "__main__":
    unittest.main()
