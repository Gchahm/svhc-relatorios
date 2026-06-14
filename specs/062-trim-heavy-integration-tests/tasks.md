# Tasks: Trim the 3 heavy integration modules + drop npx wrangler overhead

**Feature**: `062-trim-heavy-integration-tests` | **Spec**: [spec.md](./spec.md) | **Plan**: [plan.md](./plan.md)

Tests already exist (these ARE the test modules being trimmed); the "verification" is running the suite. No new test framework. The only non-test file is `scripts/common/d1.py`.

## Phase 1: Setup

- [x] T001 Capture a baseline timing of `pnpm test:py:integration` (or note the CI step-9 baseline ~1907 s) and confirm the suite currently passes, so the after-trim run is comparable. Record the three modules' current test counts (re_derive 5, reclassify 3, typed_record 3).

## Phase 2: User Story 2 — Lower per-call wrangler overhead (Priority: P2, foundational + independent)

**Goal**: Resolve the local `wrangler` binary once at import; every shell-out uses it, with an `npx wrangler` fallback. Done first because it touches the shared wrapper every test uses and is independently verifiable.

- [x] T002 [US2] In `scripts/common/d1.py`, add a module-level resolver near `_REPO_ROOT`: `_WRANGLER = [str(bin)] if (bin := _REPO_ROOT / "node_modules" / ".bin" / "wrangler").exists() else ["npx", "wrangler"]`, with a short comment explaining the per-call `npx` overhead it removes and the fallback (FR-006).
- [x] T003 [US2] In `scripts/common/d1.py`, replace the `["npx", "wrangler", …]` prefix with `[*_WRANGLER, …]` in `execute_sql`, `query`, `put_object`, and `get_object` (and any other wrangler shell-out). Keep ALL flags/args identical, including `target_flag(target)` and `_persist_args(target)` (FR-007). Do not change `--remote` paths' behavior.
- [x] T004 [US2] Verify: `python -c "import sys; sys.path.insert(0,'scripts'); from common import d1; print(d1._WRANGLER)"` prints the resolved binary path; run a quick local D1 op (e.g. `pnpm test:py:integration` will exercise it) to confirm no flag regression.

**Checkpoint**: wrangler resolver in place, fallback intact, no flag change.

## Phase 3: User Story 1 — CI stays green and faster (Priority: P1)

**Goal**: Trim the three modules' per-test reseed + redundant full-pipeline arranges without dropping coverage.

### `test_reclassify_d1.py` (singleton E3 — drop setUp restore)

- [x] T005 [US1] In `scripts/integration_tests/test_reclassify_d1.py`, remove `h.restore()` from `setUp` (keep `self._cache = tempfile.mkdtemp()`). Add a `setUp` comment justifying the removal (E3 singleton, every test re-establishes/snapshots its own subject + bystander within the test; per #106 argument). Ensure `tearDownClass` still calls `h.restore()` to reset the baseline for later modules (FR-001/FR-002). Keep all three tests and every assertion (FR-004/FR-005).

### `test_typed_record_d1.py` (own-rep E4 — drop setUp restore)

- [x] T006 [US1] In `scripts/integration_tests/test_typed_record_d1.py`, remove `h.restore()` from `setUp`. Add a `tearDownClass` that calls `h.restore()` (the module currently has none — without per-test reseed it must reset the baseline for later modules). Add a `setUp`/class comment justifying it (E4 own-representative; each test re-establishes E4 via record+apply or mark_pending). Keep all three tests and every assertion (FR-002/FR-004/FR-005).

### `test_re_derive_d1.py` (sibling/group asserts — RETAIN restore, document)

- [x] T007 [US1] In `scripts/integration_tests/test_re_derive_d1.py`, RETAIN the `setUp` `h.restore()` but add a comment explaining WHY it cannot be removed (per research.md R1 / spec A2: `test_scoped_run_leaves_out_of_scope_untouched` reads E1 as an out-of-scope baseline and `test_shared_nf_group_re_derives_together` mutates the E1/E2 pair, so a per-test clean baseline is required). Do NOT merge tests — each of the five exercises a distinct path (FR-004). No assertion dropped.

## Phase 4: Polish & verification

- [x] T008 Run `pnpm test:py:integration` — must exit 0 (SC-001). Confirm later modules in the shared process still pass (clean baseline from the tearDownClass resets).
- [x] T009 Run each trimmed module in isolation (`python -m unittest -v integration_tests.<module>` with `SVHC_WRANGLER_PERSIST=.wrangler/state-test`) — each passes standalone (US1-AC3).
- [x] T010 Compare timing vs the T001 baseline; confirm a material reduction (SC-004: fewer `restore()` + full-pipeline invocations across the three modules; reclassify/typed-record now reseed once per class via tearDownClass instead of per test, plus the npx saving).
- [x] T011 Run `node_modules/.bin/prettier --check .` — clean (SC-006). Confirm `git diff --name-only` shows only `scripts/common/d1.py` + the three test modules + the spec dir (FR-008).

## Dependencies

- T001 before everything (baseline).
- US2 (T002–T004) is independent of US1 and touches the shared wrapper; do it first so the trimmed runs already benefit.
- US1 (T005–T007) modules are independent of each other and can be edited in any order.
- Phase 4 (T008–T011) after both stories.

## Implementation Strategy

MVP = US2 (wrangler resolver, broad low-risk speedup) + US1 reclassify/typed-record drops. The re_derive module is documentation-only (retain restore). Deliver as one PR (all part of issue #108).
