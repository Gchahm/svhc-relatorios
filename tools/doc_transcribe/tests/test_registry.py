import unittest

from doc_transcribe import (
    DOC_TYPES,
    SCHEMA_VERSION,
    canonical_type,
    load_schema,
    schema_for,
    supported_types,
)
from doc_transcribe.registry import _SCHEMAS_DIR


class TestRegistry(unittest.TestCase):
    def test_every_type_resolves_to_valid_schema(self):
        for t in DOC_TYPES:
            schema = load_schema(t)
            self.assertIsInstance(schema, dict)
            self.assertEqual(schema["properties"]["doc_type"]["enum"], [t])
            self.assertEqual(schema["properties"]["schema_version"]["enum"], [SCHEMA_VERSION])

    def test_supported_types_matches_schema_files(self):
        stems = {p.stem for p in _SCHEMAS_DIR.glob("*.json")}
        self.assertEqual(set(supported_types()), stems)

    def test_aliases_resolve_to_canonical(self):
        cases = {
            "comprovante": "comprovante_pagamento",
            "payment_proof": "comprovante_pagamento",
            "comprovante de pagamento": "comprovante_pagamento",
            "NF-e": "danfe",
            "nfe": "danfe",
            "invoice": "danfe",
            "nfs-e": "nfse",
            "DANFSe": "nfse",
            "boleto bancario": "boleto",
            "Recibo": "recibo",
        }
        for raw, expected in cases.items():
            self.assertEqual(canonical_type(raw), expected, raw)
            self.assertEqual(schema_for(raw)["properties"]["doc_type"]["enum"], [expected], raw)

    def test_unknown_and_none_fall_back_to_outro(self):
        for raw in [None, "", "   ", "something weird", "xpto", "image", "other"]:
            self.assertEqual(canonical_type(raw), "outro", repr(raw))
            self.assertEqual(schema_for(raw)["properties"]["doc_type"]["enum"], ["outro"], repr(raw))

    def test_schema_for_never_raises(self):
        # Including non-string-ish inputs the type hint forbids but a caller might pass.
        for raw in [None, "", "garbage", 123, [], {}]:  # type: ignore[list-item]
            self.assertIsInstance(schema_for(raw), dict)  # type: ignore[arg-type]

    def test_load_schema_raises_on_noncanonical_key(self):
        with self.assertRaises(KeyError):
            load_schema("comprovante")  # an alias, not a canonical key
        with self.assertRaises(KeyError):
            load_schema("does_not_exist")

    def test_all_aliases_target_canonical_types(self):
        from doc_transcribe import ALIASES

        for target in ALIASES.values():
            self.assertIn(target, DOC_TYPES)

    def test_schema_version_is_string(self):
        self.assertIsInstance(SCHEMA_VERSION, str)
        self.assertEqual(SCHEMA_VERSION, "1")

    def test_union_schema_is_fully_inlined(self):
        # The API accepts a top-level anyOf but rejects $defs/$ref alongside it (EXTRACT-007:
        # "For 'anyOf', '$defs' is not supported"). The union must therefore be fully ref-inlined:
        # NO $defs and NO $ref anywhere. It must still preserve the inlined structure (e.g. danfe's
        # emitente carries the parte_emitente fields directly).
        from doc_transcribe.registry import union_schema

        u = union_schema()

        def find(node, key):
            if isinstance(node, dict):
                if key in node:
                    return True
                return any(find(v, key) for v in node.values())
            if isinstance(node, list):
                return any(find(x, key) for x in node)
            return False

        self.assertEqual([b["properties"]["doc_type"]["enum"][0] for b in u["anyOf"]], list(DOC_TYPES))
        self.assertNotIn("$defs", u)
        self.assertFalse(find(u, "$ref"), "union must be fully inlined — no $ref")
        self.assertFalse(find(u, "$defs"), "union must be fully inlined — no $defs")
        # The danfe branch's emitente was a $ref to parte_emitente — now inlined to its fields.
        danfe = next(b for b in u["anyOf"] if b["properties"]["doc_type"]["enum"] == ["danfe"])
        emit = danfe["properties"]["emitente"]["anyOf"][0]
        self.assertIn("cnpj", emit["properties"])

    def test_union_schema_does_not_mutate_cached_per_type_schema(self):
        from doc_transcribe.registry import union_schema

        union_schema()
        danfe = load_schema("danfe")
        self.assertIn("$defs", danfe)  # still self-contained
        self.assertEqual(danfe["properties"]["emitente"]["anyOf"][0]["$ref"], "#/$defs/parte_emitente")


if __name__ == "__main__":
    unittest.main()
