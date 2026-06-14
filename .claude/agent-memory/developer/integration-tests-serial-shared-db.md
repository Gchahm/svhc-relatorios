---
name: integration-tests-serial-shared-db
description: real-D1 integration modules share ONE .wrangler/state-test D1; run them serially — concurrent runs cause spurious wrangler non-zero exits + seed-timestamp mismatch failures
metadata:
  type: feedback
---

The `scripts/integration_tests/` modules all drive the SAME local Miniflare D1 at `.wrangler/state-test` (selected by `SVHC_WRANGLER_PERSIST`). Miniflare does not tolerate concurrent writers.

**Rule:** Never run two integration modules in parallel against the test DB (e.g. two background `uv run python -m unittest integration_tests.X` at once). Run them serially.

**Why:** Concurrent runs produce *spurious* failures that look like real bugs but aren't: `subprocess.CalledProcessError` from a wrangler `d1 execute` returning non-zero (DB locked/contended), and AssertionErrors on mirror-row `created_at`/`updated_at` (one run's `seed_once`/`restore` re-seeds rows mid-flight under another's read). The official suite `pnpm test:py:integration` runs everything in ONE serial process precisely for this reason.

**How to apply:** To verify a single module in isolation (the US "passes standalone" check), run it ALONE and wait for it to finish before starting the next — do not fan them out as parallel background tasks. If you see a wrangler non-zero exit or a timestamp-only mirror diff in an integration test, suspect a concurrent run before suspecting the code. Relates to [[integration-tests-shared-d1-scope]] and [[integration-tests-real-pipeline-cost]].
