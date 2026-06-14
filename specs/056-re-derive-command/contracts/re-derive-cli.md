# CLI Contract: `python -m analysis re-derive`

## Synopsis

```
python -m analysis re-derive [--periodo YYYY-MM …] [--attachment-id ID …] [--remote] [--cache-dir DIR]
```

Re-run the deterministic per-type mappers over the **stored** typed transcriptions
(`attachment_analysis_records.response`) to rebuild the `attachment_analyses` roll-ups, then
rebuild the global documents entity and refresh alerts for the affected period(s). Image-free
(no vision, no R2 image reads).

## Options

| Flag | Type | Default | Meaning |
|------|------|---------|---------|
| `--periodo` | `str …` (0+) | all periods | Restrict to these period(s) (YYYY-MM). |
| `--attachment-id` | `str …` (0+) | all classified | Restrict to these attachment ids (intersected with `--periodo` when both given). Each in-scope attachment is re-derived together with its full shared-NF group. |
| `--remote` | flag | local | Operate on production D1/R2 instead of local. Threaded through every sub-step. |
| `--cache-dir` | `str` | `../.cache/analysis` | Ephemeral scratch dir (used by the reused apply/analyze path; re-derive itself reads no images). |

No `--min-amount` / `--limit` (those are vision-cost filters for `docs-plan`/`apply-extractions`; re-derive is image-free so they do not apply).

## Behavior

1. Load the in-scope periods from D1 (period filter applied).
2. Determine the candidate attachments: those already classified (have an `attachment_analyses` row) within the loaded periods, intersected with `--attachment-id` when given.
3. Expand each candidate to its shared-NF group representative (so the whole group re-derives).
4. For each attachment with a parseable stored transcription: reconstruct its `page_classifications` staging rows from `attachment_analysis_records.response`, clear its `attachment_state.classified_at`.
5. If anything was staged: run the staging-driven `apply_extractions` (scoped to the affected periods) → `run_analysis` (scoped to the affected periods; rebuilds `documents`, refreshes alerts).
6. Print a JSON summary to stdout.

## stdout (machine-parseable summary)

A single JSON object, e.g.:

```json
{
  "re_derived": 3,
  "skipped_no_transcription": 1,
  "periods": ["2099-01"],
  "remote": false
}
```

- `re_derived` — count of attachments whose staging was reconstructed and re-applied.
- `skipped_no_transcription` — count of in-scope attachments left untouched for lack of a parseable stored transcription (FR-008/FR-012 evidence).
- `periods` — sorted list of affected period(s).
- `remote` — whether the run targeted production.

All progress/banner/log text goes to **stderr** (the logger and the `wrangler` banner), so stdout stays pure JSON.

## Exit codes

- `0` — completed (including the no-op case where nothing was re-derived).
- non-zero — an unrecoverable error (e.g. D1 unreachable); the underlying exception propagates as today's CLI does.

## Invariants (asserted by tests)

- **Image-free**: no R2 `get_object` and no image materialization occur during a re-derive. *(SC-001)*
- **Idempotent**: two consecutive runs with no mapper change leave `attachment_analyses` identical (modulo timestamps). *(SC-002)*
- **Scoped**: out-of-scope periods'/attachments' analyses, documents, and alerts are byte-identical before/after. *(SC-003)*
- **Safe**: an attachment with no parseable stored transcription is left untouched (no empty overwrite). *(SC-004)*
- **Mirror-clean**: zero writes to `entries`/`attachments`/`accountability_reports`. *(SC-005)*
