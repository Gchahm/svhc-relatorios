import unittest

from doc_transcribe import DOC_TYPES, load_schema

from doc_transcribe.tests._helpers import iter_schema_nodes

# Keywords forbidden anywhere in a schema because the API structured-output
# backend strips/rejects them (numeric/length/pattern bounds, recursion, and
# combinators outside the subset).
DISALLOWED = {
    "minimum",
    "maximum",
    "exclusiveMinimum",
    "exclusiveMaximum",
    "multipleOf",
    "minLength",
    "maxLength",
    "pattern",
    "minItems",
    "maxItems",
    "uniqueItems",
    "minProperties",
    "maxProperties",
    "format",
    "if",
    "then",
    "else",
    "not",
    "allOf",
    "oneOf",
}


def _types_of(node: dict) -> set[str]:
    t = node.get("type")
    if t is None:
        return set()
    if isinstance(t, str):
        return {t}
    if isinstance(t, list):
        return set(t)
    return set()


class TestSubsetConstraints(unittest.TestCase):
    def test_no_disallowed_keywords(self):
        for doc_type in DOC_TYPES:
            schema = load_schema(doc_type)
            for node in iter_schema_nodes(schema):
                bad = DISALLOWED & set(node.keys())
                self.assertFalse(bad, f"{doc_type}: disallowed keyword(s) {bad} in {node!r}")

    def test_every_object_forbids_additional_properties(self):
        for doc_type in DOC_TYPES:
            schema = load_schema(doc_type)
            for node in iter_schema_nodes(schema):
                # An object-typed node (or a node with properties) must declare
                # additionalProperties: false.
                if "object" in _types_of(node) or "properties" in node:
                    self.assertEqual(
                        node.get("additionalProperties"),
                        False,
                        f"{doc_type}: object node missing additionalProperties:false: {node!r}",
                    )

    def test_refs_are_local_defs_and_acyclic(self):
        for doc_type in DOC_TYPES:
            schema = load_schema(doc_type)
            defs = schema.get("$defs", {})
            for node in iter_schema_nodes(schema):
                ref = node.get("$ref")
                if ref is not None:
                    self.assertTrue(ref.startswith("#/$defs/"), f"{doc_type}: non-local $ref {ref}")
                    name = ref.split("/")[-1]
                    self.assertIn(name, defs, f"{doc_type}: $ref {ref} has no matching $defs")
            self._assert_defs_acyclic(doc_type, defs)

    def _assert_defs_acyclic(self, doc_type: str, defs: dict) -> None:
        # Build a $defs -> {referenced $defs} graph and DFS for a cycle.
        def refs_in(node: object) -> set[str]:
            found: set[str] = set()
            stack = [node]
            while stack:
                cur = stack.pop()
                if isinstance(cur, dict):
                    ref = cur.get("$ref")
                    if isinstance(ref, str) and ref.startswith("#/$defs/"):
                        found.add(ref.split("/")[-1])
                    stack.extend(cur.values())
                elif isinstance(cur, list):
                    stack.extend(cur)
            return found

        graph = {name: refs_in(body) for name, body in defs.items()}
        visiting: set[str] = set()
        done: set[str] = set()

        def visit(name: str) -> None:
            if name in done:
                return
            self.assertNotIn(name, visiting, f"{doc_type}: recursive $defs cycle at {name!r}")
            visiting.add(name)
            for nxt in graph.get(name, ()):  # nxt must be a known def
                self.assertIn(nxt, graph, f"{doc_type}: $ref to unknown def {nxt!r}")
                visit(nxt)
            visiting.discard(name)
            done.add(name)

        for name in graph:
            visit(name)


if __name__ == "__main__":
    unittest.main()
