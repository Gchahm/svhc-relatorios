"""Result-assembly / type-resolution / parse-error tests for transcribe() (EXTRACT-002, US1).

Everything is driven through an injected FakeBackend — no real `claude` subprocess, no Anthropic API,
no network.
"""

from __future__ import annotations

import json
import unittest

from doc_transcribe import SCHEMA_VERSION, transcribe
from doc_transcribe.backends import TranscribeError
from doc_transcribe.registry import DOC_TYPES
from doc_transcribe.tests._helpers import SAMPLE_PNG, FakeBackend, load_example


def _canned(doc_type: str, extra: dict | None = None) -> str:
    payload = load_example(doc_type)
    if extra:
        payload.update(extra)
    return json.dumps(payload)


class TranscribeResultTest(unittest.TestCase):
    def test_clean_result_validates_no_parse_errors(self):
        backend = FakeBackend(_canned("recibo"))
        result = transcribe(SAMPLE_PNG, "auto", backend_impl=backend)
        self.assertEqual(result["doc_type"], "recibo")
        self.assertEqual(result["schema_version"], SCHEMA_VERSION)
        self.assertNotIn("parse_errors", result)
        self.assertIn("raw_text", result["fields"])  # FR-009 evidence floor

    def test_forced_type_resolves_canonical_and_validates(self):
        # Pass a recibo body but force the type via an alias spelling.
        backend = FakeBackend(_canned("recibo"))
        result = transcribe(SAMPLE_PNG, "recibo", backend_impl=backend)
        self.assertEqual(result["doc_type"], "recibo")
        self.assertNotIn("parse_errors", result)
        # The instruction schema for a forced type is that type's schema.
        self.assertEqual(backend.calls[0]["schema"]["properties"]["doc_type"]["enum"], ["recibo"])

    def test_forced_type_alias_resolves(self):
        backend = FakeBackend(_canned("danfe"))
        result = transcribe(SAMPLE_PNG, "nf-e", backend_impl=backend)  # alias → danfe
        self.assertEqual(result["doc_type"], "danfe")

    def test_auto_uses_model_reported_type(self):
        backend = FakeBackend(_canned("boleto"))
        result = transcribe(SAMPLE_PNG, "auto", backend_impl=backend)
        self.assertEqual(result["doc_type"], "boleto")
        self.assertNotIn("parse_errors", result)

    def test_auto_presents_union_of_all_types_to_backend(self):
        # Regression (EXTRACT-007): auto mode must show the model the anyOf UNION of every type's
        # schema — not just `outro`. Showing only `outro` lets the model return raw_text but never the
        # structured fields (cnpj/numero/valores), so no documents could ever be built downstream.
        backend = FakeBackend(_canned("nfse"))
        result = transcribe(SAMPLE_PNG, "auto", backend_impl=backend)
        schema = backend.calls[0]["schema"]
        self.assertIn("anyOf", schema)
        branch_types = {b["properties"]["doc_type"]["enum"][0] for b in schema["anyOf"]}
        self.assertEqual(branch_types, set(DOC_TYPES))
        # A structured nfse response round-trips with its typed fields intact.
        self.assertEqual(result["doc_type"], "nfse")
        self.assertIn("prestador", result["fields"])
        self.assertNotIn("parse_errors", result)

    def test_forced_type_still_shows_only_that_schema(self):
        # A forced type must NOT get the union — it pins the single schema (unchanged behavior).
        backend = FakeBackend(_canned("recibo"))
        transcribe(SAMPLE_PNG, "recibo", backend_impl=backend)
        self.assertNotIn("anyOf", backend.calls[0]["schema"])
        self.assertEqual(backend.calls[0]["schema"]["properties"]["doc_type"]["enum"], ["recibo"])

    def test_canonical_stamping_overrides_bogus_echo(self):
        # Model echoes a bogus schema_version and an unknown type on an otherwise-recibo body.
        backend = FakeBackend(_canned("recibo", {"schema_version": "999", "doc_type": "recibo"}))
        result = transcribe(SAMPLE_PNG, "recibo", backend_impl=backend)
        self.assertEqual(result["schema_version"], SCHEMA_VERSION)
        self.assertEqual(result["fields"]["schema_version"], SCHEMA_VERSION)
        self.assertEqual(result["doc_type"], "recibo")

    def test_unknown_reported_type_falls_back_to_outro(self):
        backend = FakeBackend(json.dumps({"doc_type": "mystery", "schema_version": "1", "raw_text": "hi"}))
        result = transcribe(SAMPLE_PNG, "auto", backend_impl=backend)
        self.assertEqual(result["doc_type"], "outro")
        self.assertNotIn("parse_errors", result)  # outro validates clean

    def test_missing_required_field_yields_parse_errors_no_raise(self):
        # recibo body but drop raw_text (required on every type).
        payload = load_example("recibo")
        payload.pop("raw_text")
        backend = FakeBackend(json.dumps(payload))
        result = transcribe(SAMPLE_PNG, "recibo", backend_impl=backend)
        self.assertIn("parse_errors", result)
        self.assertTrue(any("raw_text" in e for e in result["parse_errors"]))

    def test_wrong_typed_field_yields_parse_errors(self):
        payload = load_example("recibo")
        payload["valor"] = "not a number"
        backend = FakeBackend(json.dumps(payload))
        result = transcribe(SAMPLE_PNG, "recibo", backend_impl=backend)
        self.assertIn("parse_errors", result)

    def test_non_json_response_becomes_outro_with_parse_error(self):
        backend = FakeBackend("Sorry, I could not read the image.")
        result = transcribe(SAMPLE_PNG, "auto", backend_impl=backend)
        self.assertEqual(result["doc_type"], "outro")
        self.assertIn("parse_errors", result)
        self.assertEqual(result["fields"]["raw_text"], "Sorry, I could not read the image.")

    def test_unknown_backend_raises_transcribe_error(self):
        with self.assertRaises(TranscribeError):
            transcribe(SAMPLE_PNG, "auto", backend="nope")

    def test_unreadable_image_raises_transcribe_error(self):
        with self.assertRaises(TranscribeError):
            transcribe("/no/such/image/path.png", "auto", backend_impl=FakeBackend(_canned("recibo")))


if __name__ == "__main__":
    unittest.main()
