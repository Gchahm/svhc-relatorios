# Contract: corrections CLI (`python -m analysis …`)

**Feature**: 054-correction-audit-trail | **Date**: 2026-06-13

Three new subcommands wrap the `scripts/analysis/corrections.py` library functions. All default to
the LOCAL D1/R2 target; `--remote` is an explicit opt-in (FR-011). stdout is the machine-readable
result (JSON); progress/logging goes to stderr.

---

## `apply-correction`

Record + apply one data correction to one attachment, gated by verify-after.

```
python -m analysis apply-correction \
    --attachment-id <id> \
    --target-finding <mismatch_key> \
    --pages '<json>' \
    [--evidence <read_path>] \
    [--agent <id>] \
    [--cache-dir <dir>] \
    [--remote]
```

- `--attachment-id` (required): the attachment to correct (a plan representative).
- `--target-finding` (required): the `mismatch_key` of the finding this correction is meant to clear
  (the same key `summarize_mismatches` rows resolve to). Used by verify-after (fail-closed if absent
  from the BEFORE set, FR-010).
- `--pages` (required): JSON mapping `{ "<page_label>": <fields-object> }` — the corrected per-page
  extraction(s), each validated against the frozen `page_classifications` contract (reusing
  `validate_page_fields`). Omit `-`/stdin alternative like `record-classification`.
- `--evidence` (optional): page image `read_path` the decision was based on (FR-013); recorded on
  each produced row. Defaults to the targeted finding's `page_refs[…].read_path` when resolvable.
- `--agent` (optional): actor id; defaults to `triage-agent` (never empty — attribution always set).
- `--cache-dir`, `--remote`: as elsewhere.

**Behavior**:
1. Resolve the affected attachment scope (the attachment + its shared-NF siblings).
2. Read the BEFORE findings (`summarize_mismatches` scoped to that set). If `--target-finding` is not
   present in BEFORE → exit non-zero, print `{"result":"unverifiable",…}`, NO data change (FR-010).
3. Snapshot the attachment's current `page_classifications` rows (`from_staging`) and compute the
   per-field diff (current page extraction vs each corrected page). If the diff is empty → print
   `{"result":"no-op",…}`, write NO row (FR-009), exit 0.
4. Apply: write the corrected staging rows (`record_classification`), `mark-pending` the attachment,
   re-run scoped `apply-extractions` → `build_documents` → scoped `analyze`.
5. Read the AFTER findings (same scope). Verify-after PASS iff target-finding gone AND no new key.
6. On PASS → write the `data_corrections` rows with `status=applied`; print
   `{"result":"applied","batch_id":…,"corrections":[…]}`, exit 0.
7. On FAIL → restore `from_staging` (atomic re-derive). On restore OK → rows `status=rolled-back`;
   print `{"result":"rolled-back","reason":…}`, exit non-zero. On restore FAIL → rows
   `status=flagged`; print `{"result":"flagged",…}`, exit non-zero.

**Idempotence (FR-012)**: re-running the identical call re-derives the same `batch_id`/row ids;
because the corrected staging already equals the live staging, step 3 sees an empty diff → no-op.

**Output (stdout, JSON)**:
```json
{
  "result": "applied | rolled-back | flagged | no-op | unverifiable",
  "batch_id": "<id or null>",
  "attachment_id": "<id>",
  "target_finding": "<mismatch_key>",
  "corrections": [ {"id","field","from","to","page","status"} ],
  "reason": "<string, present on rolled-back/flagged/unverifiable>"
}
```

---

## `list-corrections`

List recorded corrections, optionally scoped (FR-006). Read-only.

```
python -m analysis list-corrections \
    [--attachment-id <ids…>] \
    [--periodo <YYYY-MM>] \
    [--status applied|rolled-back|flagged|reverted] \
    [--remote]
```

**Output (stdout, JSON)**: a list of correction rows in a stable order (created_at desc, then id),
each carrying `{id, batch_id, attachment_id, period, page_label, field, from, to, evidence, agent,
target_finding_key, status, detail, created_at, reverted_at, reverted_by}`.

---

## `undo-correction`

Reverse a previously-applied correction (FR-007/FR-008). Restores `from_staging`, re-propagates,
records the reversal.

```
python -m analysis undo-correction \
    --id <correction-id-or-batch-id> \
    [--actor <id>] \
    [--cache-dir <dir>] \
    [--remote]
```

- `--id` (required): a correction row id OR a `batch_id` (undo reverses the whole batch — all field
  rows for that apply-correction call, since they share one `from_staging`).
- `--actor` (optional): who is undoing; defaults to `human` (never empty).

**Behavior**:
1. Load the target batch's rows. If their status is not `applied` → reject with a clear message, exit
   non-zero, NO change (FR-008).
2. Restore `from_staging` (delete the attachment's staging rows + insert the snapshot, one atomic
   batch), `mark-pending`, re-run scoped `apply-extractions` → `build_documents` → scoped `analyze`.
3. On restore OK → set the batch rows' `status=reverted`, `reverted_at`, `reverted_by`; print
   `{"result":"reverted","batch_id":…}`, exit 0.

**Output (stdout, JSON)**:
```json
{ "result": "reverted | rejected", "batch_id": "<id>", "reason": "<present when rejected>" }
```

---

## Library surface (consumed by the future triage agent, TRIAGE-004)

`scripts/analysis/corrections.py` exposes the same operations as functions (the CLI is a thin
adapter), so the agent calls them in-process without re-shelling:

- `apply_correction(attachment_id, target_finding_key, corrected_pages, *, evidence=None, agent="triage-agent", target="local", cache_dir=…) -> dict`
- `list_corrections(*, attachment_ids=None, period=None, status=None, target="local") -> list[dict]`
- `undo_correction(correction_or_batch_id, *, actor="human", target="local", cache_dir=…) -> dict`

Plus the pure helpers (unit-tested independently): `field_diff(current_fields, corrected_fields)`,
`verify_after(before_keys, after_keys, target_finding_key) -> (ok, reason)`,
`correction_row(...)`/`batch_id(...)`/`correction_id(...)` id builders, and the status-transition
guard `can_undo(status) -> bool`.
