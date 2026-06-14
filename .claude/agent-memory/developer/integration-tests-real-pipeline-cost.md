---
name: integration-tests-real-pipeline-cost
description: real-D1 integration tests are slow (~1-2s per wrangler subprocess); a full apply_extractions/run_analysis propagation costs minutes — keep this layer at smoke depth, push granular cases to mocked unit suite
metadata:
  type: project
---

The `scripts/integration_tests/` suite drives the UNSTUBBED pipeline against local Miniflare D1,
where every D1 read/write is a separate `npx wrangler d1 execute` subprocess (~1-2s startup each). A
single `apply_extractions` or `run_analysis` is a fan-out of many such subprocesses, so one
correction-lifecycle test (`_stage_and_propagate` + `apply_correction` + `undo_correction`) costs
~100s, and a 4-test module runs ~7+ min (measured: `test_corrections_d1.py` → `Ran 4 tests in
437.025s`). `pnpm test:py:integration` runs ALL integration modules in ONE shared process against a
shared D1 — minutes per module, and CI's `e2e` job runs longer still (it also installs Chromium +
runs the browser smoke). Plan for 8-15 min waits when running it locally or polling its CI check.

**Why:** Issue #100 (TEST-005) existed purely because the feature-054 corrections integration file
tripled CI (~7→22 min). Adding real-pipeline integration tests is expensive in CI minutes.

**How to apply:** Keep the integration layer at SMOKE depth (one happy path + the distinct failure
paths per surface — the documented e2e philosophy); cover granular logic in the fast MOCKED unit
suite (`scripts/tests/`, run via `pnpm test:py`, no D1/network). When tests share an identical
arrange, collapse them into one pipeline pass rather than re-running stage+apply per assertion. To
verify a single module without the whole suite: `cd scripts && uv run python -m unittest -v
integration_tests.<module>`. See [[integration-tests-shared-d1-scope]] for the shared-D1 assertion
scoping rule.
