# Contract: coverage command + config

## `scripts/.coveragerc`

```ini
[run]
source = analysis,scraper
omit =
    scraper/extractors/*
    scraper/browser.py
    scraper/runner.py
    scraper/config.py
    analysis/__main__.py
    scraper/__main__.py
    tests/*

[report]
fail_under = <FLOOR>      # recorded baseline floor (set a few points below measured total)
show_missing = false
skip_covered = false
```

- Lives in `scripts/` so `coverage` invoked with CWD `scripts/` (same as `pnpm test:py`) auto-loads it.
- `<FLOOR>` is filled after the suite is written, a small margin below the measured total.

## `package.json` script (additive — `test:py` unchanged)

```json
"test:py:cov": "cd scripts && uv run --with coverage python -m coverage run -m unittest discover -s tests -t . && uv run --with coverage python -m coverage report"
```

**Behavior contract**:
- Exit code `0` when the suite passes AND total coverage ≥ `fail_under`.
- Exit code non-zero when a test fails OR total coverage < `fail_under` (the ratchet).
- Prints a per-file + TOTAL coverage table to stdout.
- Adds NO entry to `scripts/pyproject.toml` / `uv.lock` (coverage is run-scoped via `--with`).

## `.github/workflows/ci.yml` step (additive)

A new visible step after "Python tests":

```yaml
- name: Python coverage
  run: pnpm test:py:cov
```

**Behavior contract**: the CI job fails if `pnpm test:py:cov` exits non-zero (suite failure or
coverage below floor). The existing "Python tests" step is retained (FR-009 — the plain runner keeps
working independently).
