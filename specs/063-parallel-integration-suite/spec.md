# Feature Specification: Parallelize the integration test suite across isolated workers

**Feature Branch**: `063-parallel-integration-suite`
**Created**: 2026-06-14
**Status**: Draft
**Input**: Issue #109 (DX-002) — parallelize the integration suite across workers (per-worker Miniflare D1 isolation)

## Clarifications

### Session 2026-06-14

Running unattended (no human to ask), so material ambiguities were resolved by documented assumption rather than interactive Q&A:

- Q: Worker-count bound — fixed formula vs. env override (CI cores are limited)? → A: `min(module_count, cpu_count)`, no override. CI's natural core count (2–4 on `ubuntu-latest`) already bounds it; an override is an unneeded knob (matches the issue's stated design and ~2–4× realistic speedup).
- Q: Persist-dir cleanup — leave dirs (gitignored) vs. remove after the run? → A: remove the per-worker dirs after the run (FR-008/SC-004), so nothing accumulates and each run starts clean.
- Q: Failure output — stream all workers live vs. capture and replay failing modules? → A: capture per-module output and replay only the failing module(s) at the end, keeping a parallel run's interleaved logs readable while still diagnosable on failure (FR-005).

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Parallel integration run with per-worker DB isolation (Priority: P1)

As a developer or CI runner, when I run `pnpm test:py:integration`, the real-D1 integration modules are sharded one-per-task and executed concurrently across N worker processes, each provisioning and using its **own isolated Miniflare D1/R2 state**, so the suite finishes in roughly the slowest single module's time plus one seed — not the sum of all modules — with the same overall result as the serial run.

**Why this priority**: This is the entire point of the issue — turn linear wall-clock growth into sublinear, removing the per-feature serial-minutes tax on CI. Without it there is no feature.

**Independent Test**: Run `pnpm test:py:integration` and confirm (a) it spawns multiple workers each with a distinct persist dir, (b) all tests pass, and (c) wall-clock is materially below the serial command.

**Acceptance Scenarios**:

1. **Given** the integration modules, **When** `pnpm test:py:integration` runs, **Then** modules execute in parallel worker processes, each with its own persist dir, and the overall pass/fail and the set of passing/failing tests match the serial run.
2. **Given** a passing suite, **When** run in parallel vs. serial, **Then** both report success with the same total test count.
3. **Given** one failing module, **When** run in parallel, **Then** the runner exits non-zero and surfaces that module's output so the failure is diagnosable.

---

### User Story 2 - Serial fallback for debugging one module (Priority: P2)

As a developer debugging a single failing module, I run a serial fallback command that runs all modules in one process against one shared test DB — exactly the pre-feature behavior — so I can reason about a single module without parallel-run noise.

**Why this priority**: The shared-DB serial path is the historical, well-understood debugging mode; keeping it as an escape hatch is required by the issue and protects against any parallel-runner quirk masking a real bug.

**Independent Test**: Run `pnpm test:py:integration:serial` and confirm it discovers and runs all modules in one process against the single shared `.wrangler/state-test` DB.

**Acceptance Scenarios**:

1. **Given** the serial fallback command, **When** run, **Then** it behaves exactly as the pre-feature `unittest discover` against the single shared test DB.

---

### User Story 3 - Clean, observable runs (Priority: P3)

As a developer reading CI logs, I can see the worker count and per-module timings so the speedup is visible, and I can trust that no per-worker persist dirs accumulate between runs.

**Why this priority**: Observability + cleanup are correctness/hygiene guarantees from the issue, but the suite is functional without them — hence lowest priority of the three.

**Independent Test**: Run the parallel command and confirm the log prints the worker count and a per-module timing line, and that `.wrangler/` contains no leftover `state-test-w*` dirs afterward.

**Acceptance Scenarios**:

1. **Given** a parallel run, **When** it completes (pass or fail), **Then** the per-worker persist dirs are cleaned up and the log reports the worker count and per-module timings.

### Edge Cases

- **Worker seed/migrate failure**: a worker that cannot migrate or seed its DB reports failure; the overall run fails; other workers are unaffected.
- **More modules than CPUs**: workers pull modules from a shared queue so no core is idle; a worker reuses its already-seeded DB across the modules it runs (it does not re-migrate per module).
- **Zero modules discovered**: the runner exits cleanly (success, nothing to run) — defensive.
- **Worker process crash (non-test error)**: treated as a failure for its assigned module(s) and surfaced.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: `pnpm test:py:integration` MUST discover the integration test modules and run them in parallel worker processes, sharded one-module-per-task.
- **FR-002**: Each worker MUST run against its own isolated Miniflare D1/R2 persist directory — distinct from every other worker and from the default shared test DB — selected via the existing `SVHC_WRANGLER_PERSIST` mechanism (#107).
- **FR-003**: The worker count MUST be bounded by `min(module_count, cpu_count)`.
- **FR-004**: Each worker MUST apply migrations and seed its isolated DB once before running its assigned module(s); a worker assigned multiple modules MUST reuse its seeded DB across them (no per-module re-migrate/re-seed).
- **FR-005**: The runner MUST aggregate worker/module exit codes into one overall pass/fail, exit non-zero if any module failed, and on failure surface the failing module(s) output.
- **FR-006**: A serial fallback command (`pnpm test:py:integration:serial`) MUST exist that runs all modules in one process against the single shared test DB (the pre-feature behavior).
- **FR-007**: The runner MUST print the worker count and per-module timing so the speedup is observable.
- **FR-008**: Per-worker persist dirs MUST be created under the gitignored `.wrangler/` tree and cleaned up after the run completes (pass or fail).
- **FR-009**: The CI `e2e` job MUST use the parallel path for the integration step.
- **FR-010**: The change MUST NOT introduce any D1 schema/migration change, any `src/` app-code change, or any production/`--remote` behavior change.

### Key Entities *(include if feature involves data)*

- **Integration module**: one Python module under `scripts/integration_tests/` (e.g. `test_merge_and_write_d1`). Self-contained — seeds and resets its own synthetic rows. The unit of sharding.
- **Worker**: a child OS process owning one isolated persist dir for its lifetime; seeds once, then runs one or more modules pulled from a shared module queue.
- **Persist dir**: a per-worker `.wrangler/state-test-w<i>` directory holding that worker's Miniflare D1/R2 state.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: `pnpm test:py:integration` produces the same overall pass/fail and the same set of passing/failing tests as `pnpm test:py:integration:serial`.
- **SC-002**: The parallel run's wall-clock for the integration step is materially below the serial run's (target ≈ slowest single module + one seed, not the sum of all modules).
- **SC-003**: Running concurrently produces no cross-worker interference — no spurious `wrangler` non-zero exits or seed-timestamp races caused by sharing a DB.
- **SC-004**: After any run, no orphaned per-worker persist dirs remain under `.wrangler/`.

## Assumptions

- **A-001**: Module-level sharding is sufficient; intra-module parallelism is a non-goal (it would break each module's `setUpClass`/`tearDownClass` seeding semantics).
- **A-002**: Workers are isolated *by persist directory*, not by a second D1 binding — exactly the #107 mechanism (one `DATABASE` binding).
- **A-003**: The browser e2e smoke (`pnpm test:e2e`) and the explicit `pnpm e2e:seed` step keep using the shared `.wrangler/state-test`; only the integration runner uses per-worker dirs. The CI step ordering (seed → integration → smoke) is preserved.
- **A-004**: A relative `SVHC_WRANGLER_PERSIST` value resolves against the repo root (#107), so per-worker dir names like `.wrangler/state-test-w0` are stable regardless of process CWD.
- **A-005**: Each worker is its own OS process, so `SVHC_WRANGLER_PERSIST` and the module-level migration flag are per-worker — no cross-worker race.
- **A-006**: The serial fallback uses the same shared `.wrangler/state-test` the pre-feature command used.

## Non-Goals

- Parallelizing within a module.
- Changing the per-test trims or the CI trigger (separate issues).
- Any production / `--remote` parallelism.
