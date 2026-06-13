# Quickstart: Python coverage + analysis-core tests

## Run the full Python suite (no coverage tool needed)

```bash
pnpm test:py
# → cd scripts && uv run python -m unittest discover -s tests -t .
```

## Run with coverage + ratchet

```bash
pnpm test:py:cov
# runs the suite under coverage.py (run-scoped via `uv run --with coverage`),
# then prints the coverage table and fails if total < fail_under (scripts/.coveragerc)
```

To see uncovered lines for a module while developing a test:

```bash
cd scripts && uv run --with coverage python -m coverage report --show-missing | grep attachments.py
```

## Add a new test

1. Create `scripts/tests/test_<thing>.py` with a `unittest.TestCase` subclass.
2. Build in-memory fixtures (dicts / `PeriodData` / `RefIndex`) — no D1/R2/network/playwright.
3. For a module that mixes pure logic with D1, drive the pure seam:
   - inject a `provider(attachment_id, page_label) -> (parsed|None, err|None)` into
     `build_attachment_analysis`;
   - build `PeriodData`/`RefIndex` directly for `checks`/`mismatches`;
   - use a `tempfile.TemporaryDirectory()` cache dir for `verdicts`, and
     `unittest.mock.patch("analysis.verdicts.summarize_mismatches", ...)` (stdlib) to feed
     `loop_state` a fixed mismatch list.
4. Run `pnpm test:py` then `pnpm test:py:cov`.

## Conventions (match existing tests)

- stdlib `unittest` only; no pytest, no new pip dependency.
- Tests import from `analysis.*` / `scraper.*` / `common.*` with CWD `scripts/` (the runner's `-t .`).
- Keep fixtures minimal and explicit; assert on returned objects, not on logs.
