# Tasks: Re-derive command (run mappers over stored transcriptions; no vision)

**Feature**: `056-re-derive-command` | **Spec**: [spec.md](./spec.md) | **Plan**: [plan.md](./plan.md)

Tasks are ordered by dependency. `[P]` marks tasks that could run in parallel (different files, no
ordering dependency). Tests are requested by the spec (idempotency/safety/scope are testable), so
they are included and must pass before the PR.

## T1 — Shared staging-reconstruction helper (refactor, no behavior change)

**File**: `scripts/analysis/page_classifications.py`

Extract the "stored `attachment_analysis_records.response` → `page_classifications`-shaped rows"
reconstruction into a reusable, importable seam so both `corrections` and the new `re_derive` call it:

- Add a **pure** transform `staging_rows_from_records(attachment_id, records) -> list[dict]`:
  takes already-queried `page_extraction` record dicts (with `page_label`, `page_index`, `response`
  (dict OR JSON str OR None), `parse_error`), returns staging rows shaped exactly like
  `corrections._snapshot_staging` produces (id via `page_classification_id`, decode `response`,
  map `parse_error` → `error`, `recorded_at = now_ms()`, skip rows without a `page_label`).
- Add a thin D1 reader `load_stored_records(attachment_id, target) -> list[dict]` that runs the same
  SELECT `corrections._snapshot_staging` uses (join `attachment_analysis_records` → `attachment_analyses`
  on `attachment_id`, `analysis_type='page_extraction'`).

Then refactor `corrections._snapshot_staging` to call these (`staging_rows_from_records(attachment_id,
load_stored_records(attachment_id, target))`) so there is ONE implementation. Confirm
`scripts/tests/test_corrections.py` + `scripts/integration_tests/test_corrections_d1.py` still pass
unchanged (behavior-preserving). Keep `page_classifications.py` stdlib-only.

**Acceptance**: helper exists and is pure (the transform); `corrections` snapshot output is unchanged;
existing correction tests green.

## T2 — `re_derive` orchestration function

**File**: `scripts/analysis/extractions.py`

Add `re_derive(target="local", periods_filter=None, *, attachment_ids=None, cache_dir=DEFAULT_CACHE_DIR) -> dict`:

1. `load_all_periods(target, periods_filter)`.
2. Candidate attachments = those with a persisted `attachment_analyses` row within the loaded periods
   (read from the loaded `pd.raw["attachment_analyses"]` / `pd.attachments`); intersect with
   `attachment_ids` when given.
3. Expand each candidate to its shared-NF **group** (reuse `group_attachments` on the period's
   `with_path` attachments; collect the representative + all members of any group containing a candidate)
   so the whole group re-derives. (Mirrors `select_work`'s grouping; no image reads.)
4. For each in-scope attachment: `load_stored_records` → `staging_rows_from_records` (T1). If it yields
   at least one row with a parseable `response` (a non-error staged page), write the staging rows
   (`d1.upsert_tables({"page_classifications": rows})`) and clear `attachment_state.classified_at`
   (the `corrections._clear_classified_stamp` semantics — clear ONLY the stamp, do NOT delete staging).
   Track `re_derived` vs `skipped_no_transcription`.
5. If anything was staged: run `apply_extractions(target, periods_filter=affected_periods, cache_dir=...)`
   then `run_analysis(target, periods_filter=affected_periods, cache_dir=...)` (local import of
   `run_analysis` from the package `__init__`, as `corrections._propagate` does). Redirect their stdout
   summaries to stderr so the command's JSON stays clean.
6. Return `{"re_derived": N, "skipped_no_transcription": M, "periods": sorted(affected_periods), "remote": target == "remote"}`.

Notes:
- **Image-free**: do NOT call `materialize_period_images` / any R2 read. `apply_extractions` only
  materializes when an attachment lacks `content_hash`; classified attachments are already hashed, so the
  reused apply makes no image read in the steady state (matches FR-003 — assert in the integration test).
- Reuse `_clear_classified_stamp` — extract it from `corrections` to a shared location OR replicate the
  one-line UPDATE inline (prefer reuse: import is fine since `extractions` does not import `corrections`
  today and `corrections` imports `extractions` — to avoid a cycle, put `_clear_classified_stamp` in
  `extractions.py` or `page_classifications.py` and have `corrections` import it). Decide for no import cycle.

**Acceptance**: function returns the summary dict; no image read; idempotent (re-running reproduces the
same `attachment_analyses`); skips attachments with no parseable stored record.

## T3 — CLI wiring

**File**: `scripts/analysis/__main__.py`

- Add a `re-derive` subparser: `--periodo` (nargs="*"), `--attachment-id` (nargs="*"), `--remote`,
  `--cache-dir` (reuse `_add_common` where it fits, or add the three flags explicitly + `--cache-dir`).
  No `--min-amount`/`--limit`.
- Dispatch to `re_derive(target=target, periods_filter=args.periodo, attachment_ids=args.attachment_id,
  cache_dir=args.cache_dir)` and `print(json.dumps(result, ensure_ascii=False, indent=2))`.
- Import `re_derive` from `.extractions`.
- Update the module docstring's command list to mention `re-derive`.

**Acceptance**: `python -m analysis re-derive --help` shows the flags; a run prints the JSON summary to stdout.

## T4 [P] — Unit tests (pure seams)

**File**: `scripts/tests/test_re_derive.py`

Drive the pure seams with no D1/R2/network (stdlib `unittest`, `unittest.mock.patch` for the
orchestration boundary, mirroring `test_corrections.py`):

- `staging_rows_from_records`: typed `response` dict → one staging row with decoded dict, correct id,
  `error=None`; JSON-string `response` → decoded; `parse_error` row → `error` set, `response=None`;
  row without `page_label` → skipped; empty input → `[]`.
- `re_derive` scope/skip logic with the D1 calls mocked: in-scope expansion to the group; an attachment
  whose records yield no parseable response is counted `skipped_no_transcription` and not staged; the
  no-work case returns zeros and does NOT call `apply_extractions`/`run_analysis`; the summary dict shape
  + `remote` flag.

**Acceptance**: `pnpm test:py` green; new tests exercise the documented branches.

## T5 [P] — Integration test (real D1)

**File**: `scripts/integration_tests/test_re_derive_d1.py`

Against seeded local Miniflare D1 (reuse the `_harness` + synthetic seed; scope assertions to the
synthetic `2099-01` ids per project memory — never whole-table counts):

- **Reproduce**: record a typed transcription for a synthetic attachment via `record_classification`,
  `apply_extractions`, snapshot its `attachment_analyses`; then `re_derive --periodo 2099-01`; assert the
  re-derived `attachment_analyses` equals the snapshot (ignoring `analyzed_at`). *(SC-002 reproduce.)*
- **Idempotent**: run `re_derive` twice; assert `attachment_analyses` identical (ignoring timestamps).
- **Scoped**: snapshot a second synthetic attachment outside the chosen scope; `re_derive
  --attachment-id <one>`; assert the other's analysis row is byte-identical. *(SC-003.)*
- **Safe**: an attachment with only a `parse_error` record (no parseable response) is left untouched by
  `re_derive` (its prior analysis row unchanged). *(SC-004.)*
- **Mirror-clean**: snapshot `entries`/`attachments` rows for the synthetic period before/after a
  `re_derive`; assert byte-identical. *(SC-005.)*

**Acceptance**: `pnpm test:py:integration` green.

## T6 — Quality gates + manual verification

- `pnpm lint && pnpm format` (Prettier covers the spec markdown too — run before pushing; project memory `prettier-docs-ci-gate`).
- `pnpm test:py:cov` (ratcheted coverage gate must still pass; `analysis` is in scope).
- Manual: `pnpm e2e:seed` then `python -m analysis re-derive --periodo 2099-01` twice; confirm the JSON
  summary and idempotent DB state; confirm no R2 image read in the logs.
- Record the verification (tests added + manual run) in the PR body (per the speckit `pr` phase).

**Acceptance**: all gates green; manual run reproduces the documented summary.

## Dependency order

```
T1 → T2 → T3
T1 → T4
T2/T3 → T5
T3/T4/T5 → T6
```
