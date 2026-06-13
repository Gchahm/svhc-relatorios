# Phase 0 Research: Python coverage measurement + analysis-core unit tests

## Decision 1 — Coverage tool: `coverage.py`, run-scoped via `uv run --with coverage`

**Decision**: Use `coverage.py` (the de-facto standard) but obtain it **run-scoped** with
`uv run --with coverage …` rather than adding it to `scripts/pyproject.toml` dependencies.

**Rationale**: The stdlib has no coverage measurement, so a tool is unavoidable. The repo's stance
(CLAUDE.md, constitution Principle V) is "no new dependencies unless justified". `uv run --with X`
installs `X` into an ephemeral run environment, so it never enters the project's declared deps or
`uv.lock`. Confirmed available and working in the sandbox/CI image: `coverage 7.14.1`.

**Alternatives considered**:
- Add `coverage` to project deps — rejected: violates the no-new-deps stance for a dev-only tool.
- `pytest-cov` — rejected: pulls in pytest, a whole new framework; the issue explicitly says keep
  stdlib `unittest`.
- `sys.settrace`-based homegrown coverage — rejected: reinventing a mature tool, far more code/risk.

## Decision 2 — Measured scope + exclusions

**Decision**: `coverage run --source=analysis,scraper` with omit of the playwright/wrangler
orchestration: `scraper/extractors/*`, `scraper/browser.py`, `scraper/runner.py`,
`scraper/config.py`, `analysis/__main__.py`, `scraper/__main__.py`, `tests/*`. `common/d1.py` is
out of scope (not in `--source`), since its execution paths shell out to wrangler (TEST-004).

**Rationale**: These modules need a live browser / wrangler / D1 to execute; unit tests can't drive
them without integration infrastructure (the issue's explicit out-of-scope, deferred to TEST-004).
Including them would drag the achievable percentage down for no signal. The config lives in
`scripts/.coveragerc` so the `omit`/`source`/`fail_under` travel with the repo and apply whenever
`coverage` runs from `scripts/` (the same CWD `pnpm test:py` uses).

**Measured baseline (existing 133 tests only)**: **39%** total over the in-scope set. Largest gaps:
`verdicts.py` 0%, `checks/advanced.py` 13%, `checks/trends.py` 14%, `checks/consistency.py` 14%,
`images.py` 17%, `loader.py` 16%, `vendor_match.py` 19%, `extractions.py` 21%, `attachments.py` 27%.

## Decision 3 — Ratchet via `coverage report --fail-under`

**Decision**: Enforce the floor with `coverage report --fail-under=<N>` (and persist `fail_under`
in `.coveragerc`). After the new tests land, measure the total and set the floor a few points below
it (margin for trivial refactors). Record the measured baseline % in the PR body (FR-004).

**Rationale**: `--fail-under` is the built-in ratchet — exit non-zero below the floor. A small
margin below the measured value tolerates non-functional churn while still catching real drops.
Per-module 80% (SC-001) is a target the tests aim for; the enforced gate is the global floor.

**Alternatives considered**: per-file `fail_under` via a script — rejected as over-engineering for a
first ratchet; a single global floor is the simplest enforceable gate (YAGNI).

## Decision 4 — Test style: stdlib `unittest`, pure functions, in-memory fixtures, existing seams

**Decision**: Mirror the existing `scripts/tests/` convention exactly: `unittest.TestCase` classes,
in-memory dict/dataclass fixtures, no mocking framework. For modules that mix pure logic with D1:
- `attachments.build_attachment_analysis` — inject a fake `provider` callable (the documented seam).
- `mismatches` / `checks` / `trends` / `consistency` — build `PeriodData` + `RefIndex` directly with
  `raw={"attachment_analyses": [...]}` etc.; these functions take those objects, never touch D1.
- `verdicts` — drive `record_verdict`/`loop_state` against a `tmp` cache dir; `loop_state` calls
  `summarize_mismatches` which hits D1, so test the **pure** pieces (`mismatch_key`,
  `validate_verdict`, `upsert_verdict`, `_latest_verdicts`, `_verdict_history_by_key`,
  `_upsert_history`, `load/save_verdicts_file`) and, for full `loop_state`, monkeypatch the
  module-level `summarize_mismatches` symbol with a stub (stdlib `unittest.mock.patch` is part of the
  standard library — NOT a new dependency) to feed a fixed mismatch list. This keeps D1 out.
- `extractions.build_plan` / `_page_refs_for_doc` / `mark_pending` SQL — call the pure builders with
  in-memory `periods`/`refs`; `mark_pending` is tested by asserting it returns 0 with no ids (the
  SQL-emitting path calls `d1.execute_sql`, which is the wrangler seam — not exercised).
- `documents` — `normalize_number`/`normalize_cnpj`/`document_key`/`_prune_sql`/`_sql_id_list` are
  pure; `build_documents`/`check_document_overpayment` hit D1 and are left to TEST-004.
- `images.attachments_needing_hash_backfill` is a pure read of in-memory `periods`.
- `loader._sql_str`/`_in_clause` are pure string builders.

**Rationale**: `unittest.mock.patch` is stdlib (`import unittest.mock`), so using it to stub the
already-seam'd `summarize_mismatches` does not add a dependency and does not "invoke D1" — it
*prevents* the D1 call. This honors FR-006 ("test through the existing seams … do not add a mocking
framework"): `unittest.mock` is not a third-party framework, it's the standard library.

**Alternatives considered**: refactor the modules to inject `summarize_mismatches` — rejected: the
spec is test-only, changing production signatures for testability is out of scope and riskier.

## Decision 5 — Additive command, plain runner unchanged

**Decision**: Add `"test:py:cov"` to `package.json` running coverage from `scripts/`; leave
`"test:py"` exactly as-is. Wire `test:py:cov` into `ci.yml` as a new step after "Python tests".

**Rationale**: FR-009 — a contributor without the coverage tool still runs `pnpm test:py`. CI runs
both: the plain run proves the suite passes; the coverage run proves the ratchet. (Acceptable
overlap; the suite is sub-second.)

**CI push caveat**: editing `.github/workflows/ci.yml` needs the `workflow` OAuth scope the token
lacks. The edit is committed on the branch regardless; if `git push` is rejected for the workflow
file, request a manual push (the test + `.coveragerc` + `package.json` changes are independent).
