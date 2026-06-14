---
name: re-derive-from-stored-records
description: The EXTRACT-005 re-derive path — re-run mappers over stored transcriptions (attachment_analysis_records.response) image-free, via reconstructing staging + the staging-driven apply
metadata:
  type: project
---

`python -m analysis re-derive` (feature 056, `extractions.re_derive`) is the **image-free**
propagation path parallel to `apply-extractions`: after fixing a deterministic mapper
(`type_mappers.py`), it re-runs the mappers over the **stored** typed transcriptions and rebuilds
`attachment_analyses` + documents + alerts with ZERO vision/R2-image reads.

Key seams / gotchas:

- **Source of stored transcription = `attachment_analysis_records.response`**, NOT
  `page_classifications` (feature 035 prunes staging after apply, so a steady-state classified
  attachment has no staging rows). The verbatim per-page transcription survives in the records table.
- **Shared reconstruction helper** lives in `page_classifications.py` (feature 056 refactor):
  `load_stored_records(attachment_id, target)` (the D1 SELECT) + `staging_rows_from_records(...)`
  (pure transform → `page_classifications`-shaped rows). `corrections._snapshot_staging` now calls
  these (one implementation; was duplicated). `clear_classified_stamp` also moved here (clears ONLY
  the stamp, NOT staging — `mark_pending` would wipe the staging you just wrote). Avoid an import
  cycle: `corrections` imports `extractions`, so the shared helpers go in `page_classifications`
  (imports only `common`); both call them.
- **Mechanism = reuse the staging-driven apply, never a parallel roll-up.** For each in-scope
  attachment: write reconstructed staging → `clear_classified_stamp` → then ONE
  `apply_extractions(periods_filter=affected)` + `run_analysis(periods_filter=affected)` at the end
  (local `from . import run_analysis` to dodge the cycle; redirect their stdout to stderr so the
  command's JSON summary stays clean). This guarantees byte-for-byte consistency with normal apply
  and inherits the feature-050 no-empty-overwrite safety guard + feature-024 atomic writebacks.
- **Scope** = period and/or attachment id (intersected), or global. `_redrive_scope` expands each
  in-scope attachment to its full shared-NF **group** (group_attachments off `content_hash`) because
  the staging-driven apply is group-keyed (rep + siblings must all be enrolled). Candidates = those
  with a persisted `attachment_analyses` row (i.e. classified). NOTE: an analyses row's FK is
  `attachment_id`, NOT `id` (the row's own id) — read `a["attachment_id"]`.
- **Skip-no-transcription (FR-008)**: if reconstructed staging has no parseable `response` (only
  error/empty records), DO NOT stage/clear that attachment — it's counted `skipped_no_transcription`
  and left untouched. Summary dict: `{re_derived, skipped_no_transcription, periods, remote}`.

**Integration-test gotcha**: the synthetic seed (`e2e/synthetic.py`) E1/E2/E3 carry a hand-written
`attachment_analyses` row whose `analysis_records.response` uses NON-canonical keys
(`numero`/`cnpj`, not `numero_documento`/`cnpj_emitente`), so re-deriving the raw seed does NOT
reproduce the seeded row. To test a true round-trip, classify the subject through the REAL path first
(`mark_pending` → `record_classification` → `apply_extractions`) so the baseline analysis AND the
stored record both come from your record; THEN re-derive reproduces it. E1/E2/E3 are seeded
already-classified, so `mark_pending` is required before `record_classification` or apply skips them
(apply is pending-driven via `select_work`). Related: [[typed-vs-flat-record-contract]],
[[integration-tests-shared-d1-scope]], [[pending-without-staging-destructive]].
