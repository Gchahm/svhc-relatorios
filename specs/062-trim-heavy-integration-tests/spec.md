# Feature Specification: Trim the 3 heavy integration modules + drop npx wrangler overhead

**Feature Branch**: `062-trim-heavy-integration-tests`
**Created**: 2026-06-14
**Status**: Draft
**Input**: TEST-006 / issue #108 — the CI `e2e` job's "Python integration tests (real D1 writebacks)" step is back to ~32 min because three integration modules each repeat the per-test full-reseed + full-pipeline anti-pattern; apply the proven TEST-005 / PR #106 trim and a per-call wrangler-invocation speedup.

## Why (Motivation)

The integration suite runs all modules in ONE process, serial, each `scripts/common/d1.py` call a separate `wrangler` cold-start subprocess. Since #99, three features each appended a heavy real-D1 module that, per test, runs `h.restore()` (cleanup + full synthetic re-seed) AND a full real pipeline (`apply_extractions` and/or `run_analysis`). That regressed step-9 wall-clock to ~1907 s. TEST-005 / PR #106 already proved a safe trim on `test_corrections_d1.py` (~50% fewer subprocess fan-outs, no coverage loss). This applies the same trim to the remaining three modules and resolves the local `wrangler` binary once at import so every D1/R2 shell-out skips the per-call `npx` package re-resolution.

## User Scenarios & Testing

### User Story 1 — CI stays green and faster (Priority: P1)

A maintainer pushes a change; the CI `e2e` job runs `pnpm test:py:integration`. The trimmed modules pass, the step's wall-clock is materially lower, and every distinct real-pipeline code path the three modules covered is still exercised.

**Why this priority**: This is the entire point of the issue — cut CI time without losing the coverage these tests exist for (the unstubbed `d1.py` + apply/analyze wiring).

**Acceptance Scenarios**:

1. **Given** the trimmed integration modules, **When** `pnpm test:py:integration` runs, **Then** every test passes and all later modules in the shared process still see a clean synthetic baseline.
2. **Given** the trimmed modules, **When** the suite runs, **Then** the number of full-pipeline invocations (`apply_extractions` / `run_analysis` / `re_derive`) and `h.restore()` calls is reduced versus before, while every prior assertion is retained.
3. **Given** any single trimmed module run in isolation (`python -m unittest -v integration_tests.<module>`), **When** it runs, **Then** it passes on its own (does not depend on cross-module ordering for correctness).

### User Story 2 — Lower per-call wrangler overhead (Priority: P2)

The `scripts/common/d1.py` wrapper makes hundreds of `wrangler` shell-outs per pipeline run. Resolving the local `wrangler` binary once at import removes the per-call `npx` package re-resolution overhead.

**Why this priority**: A low-risk, broad speedup that compounds across every wrangler call in the suite (and every local pipeline run), independent of the test trims.

**Acceptance Scenarios**:

1. **Given** `node_modules/.bin/wrangler` exists, **When** any D1/R2 operation runs locally, **Then** the resolved binary is invoked directly (no `npx`), with identical flags/args.
2. **Given** `node_modules/.bin/wrangler` is absent, **When** any D1/R2 operation runs, **Then** it falls back to `npx wrangler` exactly as today.
3. **Given** a `--remote` (production) operation, **When** it runs, **Then** its behavior is byte-for-byte identical to before (only the executable location changed, never the flags).

### Edge Cases

- A module that asserts on **global / shared-NF-sibling / alert** state across tests must keep its `restore()` (or scope the assertion) — removing it would let cross-test mutation leak. Each module is evaluated individually.
- Tests exercising **distinct code paths** (failure/rollback, empty/no-op, unknown-id, remote-flag reflection, schema-invalid rejection, safe-skip) must NOT be merged into the happy-path lifecycle test.
- The wrangler resolver must not break when invoked from a different CWD (the npm scripts run from `scripts/`, wrangler runs with `cwd=_REPO_ROOT`) — the binary is resolved against the repo root.

## Requirements

### Functional Requirements

- **FR-001**: For each of `test_re_derive_d1.py`, `test_reclassify_d1.py`, `test_typed_record_d1.py`, the per-test `setUp` MUST NOT call `h.restore()` UNLESS the module genuinely asserts on state that another test mutates and that the test's own arrange does not fully re-establish; where `restore()` is kept, the reason MUST be documented in a code comment.
- **FR-002**: Where `restore()` is removed, a `tearDownClass` MUST reset the synthetic baseline (`h.restore()`) so later modules in the shared process see a clean seed.
- **FR-003**: Redundant full-pipeline arranges (multiple tests that share an identical "stage subject → run pipeline" arrange and differ only in their final assertions) MUST be collapsed into one end-to-end test that preserves every assertion.
- **FR-004**: Tests exercising distinct code paths (failure/rollback, empty/no-op, unknown-id error, remote-flag reflection, schema-invalid rejection, safe-skip / no-parseable-transcription, out-of-scope-untouched, shared-NF group expansion, no-mirror-write) MUST NOT be merged away — each distinct path retains its assertions.
- **FR-005**: No assertion present before the trim may be dropped; coverage of each module's distinct paths is retained.
- **FR-006**: `scripts/common/d1.py` MUST resolve the local `wrangler` binary (`<repo>/node_modules/.bin/wrangler`) once at module import and use it for every wrangler shell-out (`execute_sql`, `query`, `put_object`, `get_object`), falling back to `["npx", "wrangler"]` only when the binary is absent.
- **FR-007**: The wrangler-invocation change MUST be flag/behavior-preserving — the `--local`/`--remote`/`--file`/`--command`/`--json` args and the `--persist-to` handling are unchanged; `--remote` (production) behavior is identical to before.
- **FR-008**: The only non-test file touched MUST be `scripts/common/d1.py`. No D1 schema change, no migration, no `src/` app-code change.

### Key Entities

- **Integration test modules** (`scripts/integration_tests/test_{re_derive,reclassify,typed_record}_d1.py`): real-D1 smoke tests driving the unstubbed `d1.py` wrapper + apply/analyze pipeline against the synthetic `2099-01` seed.
- **`_harness.py`**: provides `seed_once()` (idempotent full seed, migrations once per process) and `restore()` (cheap per-test reset of the synthetic period's analysis-owned rows).
- **`scripts/common/d1.py`**: the `wrangler`-CLI wrapper; owns every D1/R2 shell-out.

## Success Criteria

- **SC-001**: `pnpm test:py:integration` exits 0 (full suite, real Miniflare D1).
- **SC-002**: The trimmed modules' `setUp` no longer calls `h.restore()` (except where a documented per-module exception requires it); `tearDownClass` resets the baseline.
- **SC-003**: Each trimmed module's distinct paths remain covered (re-derive: reproduce+idempotent / scoped-untouched / safe-skip / no-mirror-write / shared-NF group; reclassify: record+re-derive / empty no-op / unknown-id; typed-record: typed-verbatim / legacy-flat / schema-invalid-rejected). No assertion dropped.
- **SC-004**: The total count of `h.restore()` + full-pipeline (`apply_extractions`/`run_analysis`/`re_derive`) invocations across the three modules is lower than before the trim.
- **SC-005**: `scripts/common/d1.py` invokes the resolved wrangler binary with an `npx wrangler` fallback; `--remote` behavior unchanged; no flag/arg change.
- **SC-006**: `prettier --check .` is clean; no JS/TS/schema/migration file is touched.

## Assumptions

- **A1**: The TEST-005 / PR #106 safety argument applies per-module only where the subject is a singleton attachment (no shared-NF sibling, so `_affected_scope = [subject]`), every assertion is subject-scoped, and `run_analysis` rewrites the period's alerts via an atomic DELETE+INSERT (feature 024). Each module is checked against this before removing `restore()`.
- **A2**: `test_re_derive_d1.py` has tests that assert on a sibling/out-of-scope attachment (`test_scoped_run_leaves_out_of_scope_untouched` asserts E1 is unchanged after an E3-only re-derive) and a shared-NF group (`test_shared_nf_group_re_derives_together` uses the E1/E2 pair), and interleaves classify-E3 vs classify-E1/E2 arranges. Because a prior test would otherwise leave E1/E2 (or E3) in a mutated, un-reset state that a later test's "before" snapshot reads, this module's `setUp` `restore()` is RETAINED (documented). The other two modules' subjects (E3 for reclassify; E4 for typed-record) are singletons / own-representative and bystander-scoped, so their `setUp` `restore()` is removed (matching #106) and redundant arranges merged where safe. This default is verified during implement by reading each module.
- **A3**: Verification is via the test suite itself (it IS the app surface here); no browser UI is involved — this is a non-UI change.
- **A4**: The local `wrangler` binary path is `<repo>/node_modules/.bin/wrangler` (pnpm/npm convention; matches `_REPO_ROOT` resolution already in `d1.py`).

## Dependencies

- Local Miniflare D1/R2 + an applied local migration set (the test entrypoints self-bootstrap the test DB via `SVHC_WRANGLER_PERSIST=.wrangler/state-test`).
- `wrangler` available on PATH (for the `npx` fallback) and ideally installed in `node_modules`.

## Out of Scope

- Reducing coverage of failure / no-op / remote-flag paths.
- Stubbing the real pipeline (these tests exist to exercise the unstubbed wiring).
- Parallelizing the integration suite or changing the CI trigger (separate issues).
- Any change to the mocked unit suites under `scripts/tests/`.
