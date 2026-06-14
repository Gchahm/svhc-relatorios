# Contract: `classify` subcommand

`python -m analysis classify --periodo <YYYY-MM> [--remote] [--min-amount N] [--limit N] [--backend cli|api] [--model …] [--cache-dir DIR]`

The headless, typed-only vision step. Builds the pending plan, transcribes each pending non-`recorded`
page via `doc_transcribe` (subprocess), and records the typed result to `page_classifications`. Vision
only — does NOT run apply/analyze.

## Inputs

| Flag | Type | Default | Meaning |
|------|------|---------|---------|
| `--periodo` | str* (nargs=*) | all | Period(s) to classify (YYYY-MM). |
| `--remote` | flag | local | Read/write remote (production) D1/R2 instead of local. |
| `--min-amount` | float | none | Only pending attachments for entries ≥ this amount (as `docs-plan`). |
| `--limit` | int | none | Max pending attachments (as `docs-plan`). |
| `--backend` | `cli`\|`api` | `cli` | Pass-through to `doc_transcribe --backend`. |
| `--model` | str | none | Pass-through to `doc_transcribe --model` when given. |
| `--cache-dir` | str | `../.cache/analysis` | Ephemeral scratch for materialized images. |

## Behavior

1. Load periods (`load_all_periods`), materialize images to the cache (so each page's `read_path`
   points at a local file).
2. Build the plan via `build_plan` (pending set + `--min-amount`/`--limit`); identical selection to
   `docs-plan`.
3. For each group's representative pages, for each page with `recorded == False`, **serially**:
   - run `python -m doc_transcribe --image <read_path> --type auto [--backend …] [--model …]` as a
     subprocess with `tools/` on its module path.
   - exit code `!= 0` → **config error**: stop the run, propagate the subprocess's stderr message,
     exit non-zero. No backend fallback.
   - exit code `0`: parse stdout JSON → if `parse_errors` non-empty / no usable `fields` →
     `record_classification(..., {"error": "<reason>"})`; else
     `record_classification(..., fields, typed_validator=validate_typed)`.
4. Print a summary: pages recorded (typed) / error rows / skipped (already recorded).

## Outputs

- D1 `page_classifications` rows (typed `response` or `error`).
- stdout: human summary (progress to stderr via logger).
- Exit 0 on success (including a run with only per-page errors); non-zero on a config error or a
  contract-rejection (a typed payload that fails the schema gate — should not happen with
  `doc_transcribe` output, but the gate is the safety net).

## Idempotency / scoping

- Re-running classifies only pages still `recorded == False` (the plan's per-page flag). To force a
  fresh read, `mark-pending` the attachment first (clears `classified_at` + its staging rows), then
  `classify`.
- `--periodo` / `--min-amount` / `--limit` scope exactly as `docs-plan`.

## Boundary

- `classify` reaches `doc_transcribe` ONLY via subprocess — never an import. The analysis library
  stays import-clean of `tools/` except the existing `typed_gate` validator seam (used here only to
  schema-validate the recorded typed payload).

## Test seam

`classify_period(target, periods_filter, *, cache_dir, min_amount, limit, transcribe_page=…,
typed_validator=…)` accepts an injectable `transcribe_page(read_path) -> fields-dict` callable
(default: the real subprocess runner) and an injectable `typed_validator` (default
`typed_gate.validate_typed`), so unit tests run the loop with a fake transcriber and no model/
subprocess/D1. A config error is signalled by the callable raising `ClassifyConfigError`.
