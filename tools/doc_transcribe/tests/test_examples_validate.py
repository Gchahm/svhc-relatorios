import unittest

from doc_transcribe import DOC_TYPES, validate_transcription

from doc_transcribe.tests._helpers import load_example


class TestExamplesValidate(unittest.TestCase):
    def test_each_example_validates_against_its_schema(self):
        for t in DOC_TYPES:
            with self.subTest(doc_type=t):
                example = load_example(t)
                errors = validate_transcription(example, t)
                self.assertEqual(errors, [], f"{t} example should validate; got {errors}")

    def test_danfe_example_carries_the_real_corpus_values(self):
        ex = load_example("danfe")
        self.assertEqual(ex["numero"], "000006227")
        self.assertEqual(ex["totais"]["valor_total_nota"], 2790.0)
        self.assertIn("AGUA MARINHA", ex["emitente"]["nome"])

    def test_nfse_example_carries_the_320_value(self):
        ex = load_example("nfse")
        self.assertEqual(ex["valores"]["valor_servico"], 320.0)
        self.assertEqual(ex["valores"]["valor_liquido"], 320.0)


if __name__ == "__main__":
    unittest.main()
