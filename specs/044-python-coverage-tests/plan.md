# Implementation Plan: Python coverage measurement + analysis-core unit tests

**Branch**: `044-python-coverage-tests` | **Date**: 2026-06-12 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/044-python-coverage-tests/spec.md`

## Summary

Close the unit-test gap in the analysis core and make coverage measurable + ratcheted. Add
stdlib-`unittest` test files (pure-function, in-memory fixtures, no wrangler/D1/network/playwright)
for the risk-prioritized modules — `mismatches.py`, `checks/{advanced,attachments,trends}.py`,
`nf_groups.py`, `attachments.py` (roll-up + fan-out + group amount-match), `verdicts.py`, plus
`documents.py`, `extractions.py`, `loader.py`/`images.py` pure helpers, and `vendor_match.py` as
coverage permits. Add a run-scoped coverage command (`coverage.py` via `uv run --with coverage`,
**not** a project dependency) configured in `scripts/.coveragerc` with a recorded baseline floor
that fails CI on regression, exposed as a new `test:py:cov` npm script, and wired into the TEST-001
CI workflow (`.github/workflows/ci.yml`) as a visible step.

## Technical Context

**Language/Version**: Python 3.12 (analysis/scraper under `scripts/`, run via `uv`); the test runner
is stdlib `unittest`. Node/TS unchanged.
**Primary Dependencies**: Existing only — Python stdlib (`unittest`), `scripts/common` (`det_id`,
`now_ms`, `d1.upsert_sql`). Coverage tooling is `coverage.py` obtained **run-scoped** via
`uv run --with coverage`; it is NOT added to `scripts/pyproject.toml`. No new pip/npm dependency.
**Storage**: N/A — tests read no D1/R2 and write nothing; the coverage run reads no DB.
**Testing**: stdlib `unittest`, discovered by `pnpm test:py` (`unittest discover -s tests -t .` from
`scripts/`). Coverage measured by `coverage run -m unittest discover` + `coverage report --fail-under`.
**Target Platform**: CI (ubuntu-latest, Python 3.12 via `astral-sh/setup-uv@v5`) and local dev.
**Project Type**: single (Python scripts package with a `tests/` sibling directory).
**Performance Goals**: N/A — the suite already runs in <1s; coverage adds negligible overhead.
**Constraints**: No new project dependency; no mocking framework; tests must not invoke
wrangler/D1/network/playwright; the plain `pnpm test:py` must keep working without the coverage tool.
**Scale/Scope**: ~8-12 new test files under `scripts/tests/`; one `.coveragerc`; one npm script; one
CI step. Coverage scope: `scripts/analysis/` + `scripts/scraper/` minus the playwright/wrangler
orchestration (`runner.py`, `browser.py`, `config.py`, `extractors/`, both `__main__.py`,
`common/d1.py`).

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- **I. Type Safety & Schema Discipline**: N/A — no schema change, no TS change, no auth change. PASS.
- **II. Cloudflare-Native Architecture**: N/A — no DB access added; tests deliberately avoid D1/R2.
  PASS.
- **III. Quality Gates Before Commit**: This feature *is* a quality gate. Tests are added because the
  spec (TEST-002) explicitly requests them, exactly the condition under which Principle III mandates
  they pass before merge. `pnpm lint`/`pnpm format` will run before commit; Python files are not
  Prettier-formatted but the `.coveragerc`/`package.json`/`ci.yml` edits will be. PASS.
- **IV. Security & Auth by Default**: N/A — no routes, no data exposure. PASS.
- **V. Simplicity & Incremental Delivery**: Run-scoped `coverage.py` (no new declared dependency)
  and stdlib `unittest` (no new framework) are the simplest options satisfying the requirement;
  delivered as independent slices (tests, then gate, then CI wiring) ordered by priority. PASS.

No violations — Complexity Tracking left empty.

## Project Structure

### Documentation (this feature)

```text
specs/044-python-coverage-tests/
├── plan.md              # This file
├── spec.md              # Phase: specify
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output (the test-fixture shapes + module contracts under test)
├── quickstart.md        # Phase 1 output (how to run coverage + add a test)
├── contracts/           # Phase 1 output (coverage-command contract)
└── tasks.md             # Phase 2 output (speckit tasks)
```

### Source Code (repository root)

```text
scripts/
├── .coveragerc                      # NEW — coverage scope (source/omit) + fail-under floor
├── analysis/                        # modules under test (unchanged by this feature)
│   ├── mismatches.py
│   ├── nf_groups.py
│   ├── attachments.py
│   ├── vendor_match.py
│   ├── verdicts.py
│   ├── documents.py
│   ├── extractions.py
│   ├── loader.py
│   ├── images.py
│   └── checks/{advanced,attachments,trends}.py
└── tests/                           # NEW test files (stdlib unittest), e.g.:
    ├── test_mismatches.py
    ├── test_check_attachments.py
    ├── test_check_advanced.py
    ├── test_check_trends.py
    ├── test_nf_groups.py
    ├── test_attachments_rollup.py
    ├── test_verdicts.py
    ├── test_documents_build.py
    ├── test_extractions_plan.py
    ├── test_images_loader.py
    └── test_vendor_match.py

package.json                          # MODIFIED — add "test:py:cov" script
.github/workflows/ci.yml              # MODIFIED — add "Python coverage" step (may need manual push)
```

**Structure Decision**: Single Python `scripts/` package with a sibling `tests/` directory, matching
the existing convention (15 test files discovered by `unittest discover -s tests -t .`). New tests
live alongside them; coverage config is a `scripts/.coveragerc` so `coverage` invoked from `scripts/`
(the same CWD `test:py` uses) picks it up automatically.

## Complexity Tracking

> No constitution violations — section intentionally empty.
