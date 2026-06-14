# Research: Trim the 3 heavy integration modules + drop npx wrangler overhead

## R1 — Per-module `restore()` removal safety

**Decision**: Remove `setUp` `h.restore()` from `test_reclassify_d1.py` and `test_typed_record_d1.py`; **retain** it in `test_re_derive_d1.py` (documented).

**Rationale**:

The TEST-005 / PR #106 safety argument for dropping per-test `restore()`: (a) the subject attachment is a **singleton** (no shared-NF sibling, so the affected scope is `[subject]`), (b) every assertion is **subject-scoped**, (c) each test fully re-establishes its subject via `mark_pending → record_classification → apply_extractions`, and (d) `run_analysis` rewrites the period's alerts via an atomic DELETE+INSERT so nothing accumulates. Evaluated per module:

- **`test_reclassify_d1.py`** — subject is **E3** (singleton, NF-1002, no sibling). Tests:
  - `test_reclassify_records_and_re_derives`: snapshots the **bystander E1** (`before_other`) inside the test, reclassifies E3, asserts E1 unchanged. The bystander snapshot is taken *within* the same test, so it never reads stale cross-test state — and E1 is never written by any test here. E3 is fully re-established by `reclassify` (which records staging + propagates).
  - `test_empty_pages_is_no_op`: snapshots E3's `classified_at` within the test, asserts unchanged after an empty-pages no-op.
  - `test_unknown_attachment_raises`: bogus id, asserts nothing recorded.
  None of the three reads cross-test state for a subject another test mutated and that it does not itself re-establish. → **Drop `setUp` `restore()`; move baseline reset to `tearDownClass`.** A bystander-snapshot caveat: E1 is the seeded baseline and no test writes E1, so reclassifying E3 leaves it byte-identical across the whole module run. The first test's `before_other` reads the seeded value (seed_once ran in setUpClass); safe.

- **`test_typed_record_d1.py`** — subject is **E4** (seeded PENDING single-entry, its own shared-NF representative, page `p1`). Every test re-establishes E4 (record + apply, or `mark_pending` then assert no write), and every assertion reads E4's `attachment_analysis_records.response` / `attachment_analyses` row by E4's ids. `test_schema_invalid_typed_rejected_no_staging_write` does `mark_pending(E4)` then asserts `page_classifications` count == 0 for E4 and that an invalid record raises and writes nothing — this is robust regardless of E4's prior staging because `mark_pending` clears it. → **Drop `setUp` `restore()`; move baseline reset to `tearDownClass`.**

- **`test_re_derive_d1.py`** — **RETAIN** `setUp` `restore()`. This module is NOT singleton/subject-scoped across the board:
  - `test_scoped_run_leaves_out_of_scope_untouched` snapshots **E1 (out of scope)** as a baseline and asserts it is unchanged after an E3-only re-derive.
  - `test_shared_nf_group_re_derives_together` classifies the **E1+E2 shared-NF pair** to 300 and re-derives the group.
  - `test_no_mirror_table_writes` reads E3's seeded mirror rows.
  Without `restore()`, the order in which these run would leave E1/E2 mutated (group test → 300) or E3 in a prior state, and a later test reading "E1 before" / a seeded baseline would observe carried-over state. The arranges genuinely depend on a clean per-test baseline. Removing `restore()` here is unsafe per the spec's edge-case rule (asserts on sibling/out-of-scope state). → **Keep `restore()` (documented in a `setUp` comment).** The trim for this module is limited to FR-003 arrange merges only where two tests share an identical `_classify_e3()`-then-assert arrange and differ only in final assertions — but the five tests each exercise a **distinct** path (reproduce+idempotent / scoped-untouched / safe-skip / no-mirror-write / shared-NF group), so per FR-004 none may be merged away. Net for re_derive: **no test-count reduction**; its share of the speedup comes from the `npx wrangler` removal (R2).

**Alternatives considered**: (1) Scope the re_derive assertions to make them order-independent and drop `restore()` too — rejected: it would rewrite assertions (risking dropped coverage) for marginal gain, and re_derive's full-pipeline cost is dominated by `apply_extractions` which the merges can't remove (each path needs its own arrange). (2) Merge all four reclassify/typed paths into one — rejected: they exercise distinct paths (no-op, unknown-id, schema-invalid) that FR-004 forbids merging.

## R2 — `npx wrangler` → resolved local binary

**Decision**: Add a module-level resolver in `scripts/common/d1.py`:
`_WRANGLER = [str(_REPO_ROOT / "node_modules" / ".bin" / "wrangler")]` when that file exists, else `["npx", "wrangler"]`. Use `[*_WRANGLER, …]` in `execute_sql`, `query`, `put_object`, `get_object`.

**Rationale**: `npx` re-resolves the package on each call; a single pipeline run makes hundreds of wrangler shell-outs. Resolving the binary path once at import (against `_REPO_ROOT`, which `d1.py` already computes) removes that per-call overhead. The flags/args (`--local`/`--remote`/`--file`/`--command`/`--json`/`--persist-to`) are unchanged, so `--remote` (production) behavior is byte-for-byte identical. The fallback preserves behavior when `node_modules/.bin/wrangler` is absent (e.g. a global-only wrangler install).

**Alternatives considered**: (1) `shutil.which("wrangler")` — rejected: would pick a global wrangler over the repo-pinned version, a behavior change. (2) Cache the npx resolution via env — rejected: more complex, less direct than pointing at the known bin path. (3) Keep `npx` — rejected: that is the overhead the issue calls out.

## R3 — Verification approach

**Decision**: Verify via the integration suite itself (`pnpm test:py:integration`) plus per-module isolated runs (`python -m unittest -v integration_tests.<module>`), and `prettier --check .`. No browser/UI involved.

**Rationale**: This is a test/infra change; the "running app" here is the unstubbed `d1.py` + apply/analyze pipeline that the integration suite drives against real Miniflare D1. A green full-suite run proves the trimmed modules pass AND that later modules in the shared process still see a clean baseline (the `tearDownClass` reset). Timing the run before/after demonstrates the speedup.
