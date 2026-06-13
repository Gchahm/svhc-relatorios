"""Backend tests: extract_json recovery, CliBackend argv/errors, ApiBackend request/errors, optional-dep.

All without executing a real `claude` subprocess or hitting the Anthropic API (stubbed/monkeypatched).
"""

from __future__ import annotations

import builtins
import json
import os
import subprocess
import sys
import unittest
from pathlib import Path

from doc_transcribe import schema_for, transcribe
from doc_transcribe.backends import (
    ApiBackend,
    CliBackend,
    TranscribeError,
    extract_json,
    media_type_for,
)
from doc_transcribe.tests._helpers import SAMPLE_PNG, FakeBackend, load_example


class ExtractJsonTest(unittest.TestCase):
    def test_clean_json(self):
        self.assertEqual(extract_json('{"a": 1}'), {"a": 1})

    def test_fenced_json(self):
        self.assertEqual(extract_json('```json\n{"a": 1}\n```'), {"a": 1})

    def test_bare_fence(self):
        self.assertEqual(extract_json('```\n{"a": 1}\n```'), {"a": 1})

    def test_prose_wrapped(self):
        self.assertEqual(extract_json('Here is the result:\n{"a": {"b": 2}}\nDone.'), {"a": {"b": 2}})

    def test_leading_trailing_whitespace(self):
        self.assertEqual(extract_json('   \n {"a": 1}\n  '), {"a": 1})

    def test_brace_in_string_literal_balances(self):
        self.assertEqual(extract_json('prefix {"a": "x } y"} suffix'), {"a": "x } y"})

    def test_garbage_returns_none(self):
        self.assertIsNone(extract_json("not json at all"))

    def test_non_object_json_returns_none(self):
        self.assertIsNone(extract_json("[1, 2, 3]"))

    def test_non_string_returns_none(self):
        self.assertIsNone(extract_json(None))  # type: ignore[arg-type]


class MediaTypeTest(unittest.TestCase):
    def test_png_bytes(self):
        self.assertEqual(media_type_for(SAMPLE_PNG), "image/png")

    def test_extension(self):
        self.assertEqual(media_type_for("a.jpg"), "image/jpeg")
        self.assertEqual(media_type_for("a.JPEG"), "image/jpeg")

    def test_default_png(self):
        self.assertEqual(media_type_for("a.unknown"), "image/png")


class CliBackendTest(unittest.TestCase):
    def test_missing_claude_binary_raises(self):
        backend = CliBackend()
        import doc_transcribe.backends as be

        orig = be.shutil.which
        be.shutil.which = lambda _name: None
        try:
            with self.assertRaises(TranscribeError):
                backend.transcribe_to_json(
                    image_bytes=SAMPLE_PNG, media_type="image/png", schema={}, instruction="x"
                )
        finally:
            be.shutil.which = orig

    def test_builds_argv_and_returns_stdout(self):
        backend = CliBackend(model="opus")
        import doc_transcribe.backends as be

        captured: dict = {}

        def fake_run(argv, **kwargs):
            captured["argv"] = argv
            captured["kwargs"] = kwargs

            class P:
                returncode = 0
                stdout = '{"doc_type": "outro", "schema_version": "1", "raw_text": "hi"}'
                stderr = ""

            return P()

        orig_run = be.subprocess.run
        orig_which = be.shutil.which
        be.subprocess.run = fake_run
        be.shutil.which = lambda _n: "/usr/bin/claude"
        try:
            out = backend.transcribe_to_json(
                image_bytes=SAMPLE_PNG, media_type="image/png", schema={}, instruction="INSTR"
            )
        finally:
            be.subprocess.run = orig_run
            be.shutil.which = orig_which

        argv = captured["argv"]
        self.assertEqual(argv[:4], ["claude", "-p", "--output-format", "text"])
        self.assertIn("--model", argv)
        self.assertIn("opus", argv)
        self.assertIn("--add-dir", argv)
        # The prompt is fed via stdin (not a positional arg).
        self.assertIn("INSTR", captured["kwargs"]["input"])
        self.assertIn("doc_type", out)

    def test_nonzero_exit_raises(self):
        backend = CliBackend()
        import doc_transcribe.backends as be

        def fake_run(argv, **kwargs):
            class P:
                returncode = 1
                stdout = ""
                stderr = "boom"

            return P()

        orig_run = be.subprocess.run
        orig_which = be.shutil.which
        be.subprocess.run = fake_run
        be.shutil.which = lambda _n: "/usr/bin/claude"
        try:
            with self.assertRaises(TranscribeError):
                backend.transcribe_to_json(
                    image_bytes=SAMPLE_PNG, media_type="image/png", schema={}, instruction="x"
                )
        finally:
            be.subprocess.run = orig_run
            be.shutil.which = orig_which


class ApiBackendBuildRequestTest(unittest.TestCase):
    def test_build_request_puts_schema_as_json_schema_and_image_block(self):
        backend = ApiBackend()
        schema = schema_for("recibo")
        req = backend.build_request(
            image_bytes=SAMPLE_PNG, media_type="image/png", schema=schema, instruction="INSTR"
        )
        self.assertEqual(req["model"], "claude-opus-4-8")
        self.assertEqual(req["output_config"]["format"]["type"], "json_schema")
        self.assertIs(req["output_config"]["format"]["schema"], schema)
        content = req["messages"][0]["content"]
        kinds = [b["type"] for b in content]
        self.assertIn("image", kinds)
        self.assertIn("text", kinds)
        image_block = next(b for b in content if b["type"] == "image")
        self.assertEqual(image_block["source"]["media_type"], "image/png")
        self.assertEqual(image_block["source"]["type"], "base64")
        # No deprecated sampling params on Opus 4.8.
        self.assertNotIn("temperature", req)
        self.assertEqual(req["thinking"], {"type": "adaptive"})


class ApiBackendErrorTest(unittest.TestCase):
    def _without_anthropic(self):
        orig_import = builtins.__import__

        def fake_import(name, *args, **kwargs):
            if name == "anthropic" or name.startswith("anthropic."):
                raise ImportError("no anthropic")
            return orig_import(name, *args, **kwargs)

        return orig_import, fake_import

    def test_missing_sdk_raises_clear_error(self):
        backend = ApiBackend()
        orig_import, fake_import = self._without_anthropic()
        saved = sys.modules.pop("anthropic", None)
        builtins.__import__ = fake_import
        try:
            with self.assertRaises(TranscribeError) as cm:
                backend.transcribe_to_json(
                    image_bytes=SAMPLE_PNG, media_type="image/png", schema={}, instruction="x"
                )
            self.assertIn("anthropic", str(cm.exception).lower())
        finally:
            builtins.__import__ = orig_import
            if saved is not None:
                sys.modules["anthropic"] = saved

    def test_missing_key_raises_clear_error(self):
        backend = ApiBackend()
        # Stub a minimal anthropic module so the import succeeds but the key check fires.
        fake = type(sys)("anthropic")
        fake.Anthropic = lambda *a, **k: None  # type: ignore[attr-defined]
        sys.modules["anthropic"] = fake
        saved_key = os.environ.pop("ANTHROPIC_API_KEY", None)
        try:
            with self.assertRaises(TranscribeError) as cm:
                backend.transcribe_to_json(
                    image_bytes=SAMPLE_PNG, media_type="image/png", schema={}, instruction="x"
                )
            self.assertIn("ANTHROPIC_API_KEY", str(cm.exception))
        finally:
            del sys.modules["anthropic"]
            if saved_key is not None:
                os.environ["ANTHROPIC_API_KEY"] = saved_key

    def test_stubbed_client_returns_json(self):
        backend = ApiBackend()

        class _TextBlock:
            type = "text"
            text = '{"doc_type": "recibo", "schema_version": "1", "raw_text": "x", "valor": 1.0}'

        class _Message:
            content = [_TextBlock()]

        class _Messages:
            def create(self, **kwargs):
                return _Message()

        class _Client:
            messages = _Messages()

        fake = type(sys)("anthropic")
        fake.Anthropic = lambda *a, **k: _Client()  # type: ignore[attr-defined]
        sys.modules["anthropic"] = fake
        os.environ["ANTHROPIC_API_KEY"] = "test-key"
        try:
            out = backend.transcribe_to_json(
                image_bytes=SAMPLE_PNG, media_type="image/png", schema=schema_for("recibo"), instruction="x"
            )
            self.assertIn("recibo", out)
            # And the full transcribe() path re-validates above the backend (SC-003).
            result = transcribe(SAMPLE_PNG, "recibo", backend="api", backend_impl=backend)
            self.assertEqual(result["doc_type"], "recibo")
        finally:
            del sys.modules["anthropic"]
            os.environ.pop("ANTHROPIC_API_KEY", None)


class OptionalDepInvariantTest(unittest.TestCase):
    def test_cli_path_works_without_anthropic_or_key(self):
        # transcribe() via cli backend must work with the SDK unimportable and no key.
        orig_import = builtins.__import__

        def fake_import(name, *args, **kwargs):
            if name == "anthropic" or name.startswith("anthropic."):
                raise ImportError("no anthropic")
            return orig_import(name, *args, **kwargs)

        saved = sys.modules.pop("anthropic", None)
        saved_key = os.environ.pop("ANTHROPIC_API_KEY", None)
        builtins.__import__ = fake_import
        try:
            result = transcribe(SAMPLE_PNG, "recibo", backend_impl=FakeBackend(json.dumps(load_example("recibo"))))
            self.assertEqual(result["doc_type"], "recibo")
        finally:
            builtins.__import__ = orig_import
            if saved is not None:
                sys.modules["anthropic"] = saved
            if saved_key is not None:
                os.environ["ANTHROPIC_API_KEY"] = saved_key

    def test_no_scripts_analysis_import_in_module(self):
        module_root = Path(__file__).resolve().parent.parent
        for py in module_root.glob("*.py"):
            text = py.read_text(encoding="utf-8")
            self.assertNotIn("scripts.analysis", text, f"{py.name} must not import scripts.analysis")
            self.assertNotIn("from analysis", text, f"{py.name} must not import the analysis package")


if __name__ == "__main__":
    unittest.main()
