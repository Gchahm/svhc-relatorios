"""Tests for the local-DB persist selector (feature 061 / issue #107).

Covers the pure ``common.d1._persist_args`` helper: the ``SVHC_WRANGLER_PERSIST`` env var selects an
isolated Miniflare persist dir for LOCAL wrangler calls, is resolved against the repo root when
relative, used as-is when absolute, and is NEVER applied to ``--remote``.

Run: ``python -m unittest discover -s tests -t .`` (from scripts/).
"""

import os
import unittest
from pathlib import Path
from unittest import mock

from common import d1


class PersistArgsTest(unittest.TestCase):
    @mock.patch.dict(os.environ, {}, clear=True)
    def test_unset_is_empty(self):
        self.assertEqual(d1._persist_args("local"), [])

    @mock.patch.dict(os.environ, {d1._PERSIST_ENV: ""}, clear=True)
    def test_empty_string_is_empty(self):
        # An explicitly-empty value is treated as unset (staging default).
        self.assertEqual(d1._persist_args("local"), [])

    @mock.patch.dict(os.environ, {d1._PERSIST_ENV: ".wrangler/state-test"}, clear=True)
    def test_relative_resolves_against_repo_root(self):
        args = d1._persist_args("local")
        self.assertEqual(args[0], "--persist-to")
        resolved = Path(args[1])
        self.assertTrue(resolved.is_absolute())
        self.assertEqual(resolved, d1._REPO_ROOT / ".wrangler/state-test")

    @mock.patch.dict(os.environ, {d1._PERSIST_ENV: "/abs/state-test"}, clear=True)
    def test_absolute_used_as_is(self):
        self.assertEqual(d1._persist_args("local"), ["--persist-to", "/abs/state-test"])

    @mock.patch.dict(os.environ, {d1._PERSIST_ENV: ".wrangler/state-test"}, clear=True)
    def test_remote_never_redirected(self):
        # Even with the var set, a production (--remote) call gets no --persist-to.
        self.assertEqual(d1._persist_args("remote"), [])

    @mock.patch.dict(os.environ, {}, clear=True)
    def test_remote_unset_is_empty(self):
        self.assertEqual(d1._persist_args("remote"), [])


if __name__ == "__main__":
    unittest.main()
