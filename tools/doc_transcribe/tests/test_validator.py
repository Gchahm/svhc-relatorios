import unittest

from doc_transcribe import schema_for, validate, validate_transcription

from doc_transcribe.tests._helpers import load_example


def _valid_nfse() -> dict:
    return load_example("nfse")


class TestValidatorPositive(unittest.TestCase):
    def test_valid_payload_passes(self):
        self.assertEqual(validate_transcription(_valid_nfse(), "nfse"), [])

    def test_nullable_union_accepts_null(self):
        payload = _valid_nfse()
        payload["valores"]["valor_liquido"] = None  # number|null
        self.assertEqual(validate_transcription(payload, "nfse"), [])

    def test_anyOf_object_or_null(self):
        payload = _valid_nfse()
        payload["prestador"] = None  # anyOf object|null
        self.assertEqual(validate_transcription(payload, "nfse"), [])


class TestValidatorNegative(unittest.TestCase):
    def test_missing_required_field(self):
        payload = _valid_nfse()
        del payload["doc_type"]
        errors = validate_transcription(payload, "nfse")
        self.assertTrue(any("missing required field 'doc_type'" in e for e in errors), errors)

    def test_wrong_type(self):
        payload = _valid_nfse()
        payload["valores"]["valor_liquido"] = "320,00"  # string where number|null expected
        errors = validate_transcription(payload, "nfse")
        self.assertTrue(
            any("valores.valor_liquido" in e and "expected" in e for e in errors), errors
        )

    def test_unexpected_key_rejected(self):
        payload = _valid_nfse()
        payload["totally_unknown"] = 1
        errors = validate_transcription(payload, "nfse")
        self.assertTrue(any("unexpected key 'totally_unknown'" in e for e in errors), errors)

    def test_unexpected_nested_key_rejected(self):
        payload = _valid_nfse()
        payload["valores"]["bogus"] = 1
        errors = validate_transcription(payload, "nfse")
        self.assertTrue(any("$.valores" in e and "bogus" in e for e in errors), errors)

    def test_out_of_enum(self):
        payload = _valid_nfse()
        payload["doc_type"] = "danfe"  # wrong type value for the nfse schema's enum
        errors = validate(payload, schema_for("nfse"))
        self.assertTrue(any("$.doc_type" in e and "enum" in e for e in errors), errors)

    def test_non_object_root(self):
        errors = validate(["not", "an", "object"], schema_for("nfse"))
        self.assertEqual(len(errors), 1, errors)
        self.assertTrue(errors[0].startswith("$:"), errors)
        self.assertIn("expected object", errors[0])

    def test_bool_is_not_number(self):
        payload = _valid_nfse()
        payload["valores"]["valor_liquido"] = True
        errors = validate_transcription(payload, "nfse")
        self.assertTrue(any("valor_liquido" in e and "bool" in e for e in errors), errors)

    def test_comprovante_tipo_enum(self):
        payload = load_example("comprovante_pagamento")
        payload["tipo"] = "cheque"  # not in enum
        errors = validate_transcription(payload, "comprovante_pagamento")
        self.assertTrue(any("$.tipo" in e and "enum" in e for e in errors), errors)

    def test_array_item_validation(self):
        payload = load_example("danfe")
        payload["itens"][0]["quantidade"] = "two"  # number|null expected
        errors = validate_transcription(payload, "danfe")
        self.assertTrue(any("$.itens[0].quantidade" in e for e in errors), errors)

    def test_anyOf_no_branch_matches(self):
        payload = _valid_nfse()
        payload["prestador"] = "a string"  # neither object nor null
        errors = validate_transcription(payload, "nfse")
        self.assertTrue(any("$.prestador" in e for e in errors), errors)


class TestValidatorErrors(unittest.TestCase):
    def test_malformed_schema_raises(self):
        with self.assertRaises(ValueError):
            validate({}, "not a dict")  # type: ignore[arg-type]


if __name__ == "__main__":
    unittest.main()
