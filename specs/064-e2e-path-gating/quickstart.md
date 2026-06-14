# Quickstart: Verify the e2e path-gating

## What changed

- `.github/workflows/ci.yml` now holds **only** the `verify` job (lint/format/tests/typecheck), still on every PR and every push to `main`.
- `.github/workflows/ci-e2e.yml` is **new** and holds the `e2e` job (integration + browser smoke). It runs on every push to `main`, and on a PR **only when** a relevant path changed.

## Static verification (local, no run needed)

```bash
# Both files parse and (if installed) pass actionlint
python3 -c "import yaml,sys; [yaml.safe_load(open(f)) for f in ['.github/workflows/ci.yml','.github/workflows/ci-e2e.yml']]; print('YAML OK')"
command -v actionlint >/dev/null && actionlint .github/workflows/ci.yml .github/workflows/ci-e2e.yml || echo "actionlint not installed — skipped"

# ci.yml has verify, not e2e
grep -q 'verify:' .github/workflows/ci.yml && ! grep -q 'pnpm test:e2e' .github/workflows/ci.yml && echo "ci.yml OK"

# ci-e2e.yml has the e2e steps + timeout + paths
grep -q 'timeout-minutes' .github/workflows/ci-e2e.yml && grep -q 'pnpm test:e2e' .github/workflows/ci-e2e.yml && echo "ci-e2e.yml OK"

# Formatting gate (constitution III) — must be clean before commit
pnpm format:check
```

## Live verification (on the PR)

- This PR itself touches `.github/workflows/ci-e2e.yml` (a relevant path) **and** `specs/**` (docs). Per the trigger matrix it should run **both** `verify` and `e2e` — confirming C2/C6/C7.
- Confirm in the PR Checks tab: both `CI / verify` and `CI e2e / e2e` appear.
- After merge, the push to `main` runs both (C8).

## Verification recorded for the PR body

Because this is a GitHub Actions config change with no app-facing surface, "verification" is: (1) the static checks above pass locally, and (2) the PR's own Checks tab demonstrates the trigger matrix. There is no app screen to drive.
