# Phase 0 Research: All-CLI typed document transcription

## R1. How to launch `doc_transcribe` as a subprocess from the analysis pipeline

**Decision**: Invoke `[sys.executable, "-m", "doc_transcribe", "--image", read_path, "--type",
"auto", "--backend", backend, ...("--model", model)]` with the subprocess's working directory /
module search path set so `import doc_transcribe` resolves. The analysis CLI runs with `cwd =
scripts/`, where `tools/` is off the path; resolve `<repo>/tools` exactly as `typed_gate` does
(`Path(__file__).resolve().parents[2] / "tools"`) and run the subprocess with `cwd=<that dir>` (and
also export it on `PYTHONPATH` for robustness). Capture stdout/stderr; `returncode != 0` is a config
error; `returncode == 0` parses stdout as the JSON result.

**Rationale**: This is the explicit boundary the issue mandates ("subprocess, never an import"). It
keeps the analysis *library* import-clean of `tools/` (the only import seam stays `typed_gate`). Using
`sys.executable` keeps the same interpreter/venv. Mirroring `typed_gate`'s `parents[2]` path
resolution means one consistent rule for locating `tools/`.

**Alternatives considered**:
- *Import `doc_transcribe.transcribe()` directly* — rejected: violates FR-005 / the issue's explicit
  "subprocess, never an import" boundary and re-couples the library to `tools/`.
- *Run `python -m doc_transcribe` from the current cwd relying on `PYTHONPATH` only* — rejected as
  the sole mechanism (CWD-as-tools is the simpler/robust primary; PYTHONPATH is belt-and-suspenders).

## R2. Result shape and per-page failure detection

**Decision**: `doc_transcribe`'s CLI prints `{"doc_type", "schema_version", "fields"[,
"parse_errors"]}` and exits 0 even on a bad model response. `classify` takes `result["fields"]` (the
typed object carrying `doc_type`/`schema_version`) and records it via `record_classification`. A
**per-page failure** is signalled by a **non-empty `result["parse_errors"]`** (or a missing/empty
`fields`); in that case `classify` records `{"error": "<joined parse_errors / reason>"}` for that
page and continues.

**Rationale**: `parse_errors` is `doc_transcribe`'s documented "bad model response, not a config
error" signal (transcribe.py: present ONLY when non-empty; the `_NO_JSON_ERROR` case also sets it).
Recording an error row (not aborting) matches the existing `D1ExtractionProvider` error semantics and
FR-007. Using the typed `fields` (not the whole envelope) matches what `record_classification`
stores and what `to_reconciliation_fields` reads (`fields` carries its own `doc_type`).

**Alternatives considered**:
- *Store the whole envelope* — rejected: the gate + roll-up read the per-type `fields` object; the
  envelope's outer `doc_type`/`schema_version` are duplicated inside `fields` (transcribe.py stamps
  them onto `fields`), so `fields` is self-describing and is the canonical stored shape (matches the
  existing typed-record persistence in feature 055).

## R3. Config / environment error handling (stop the run)

**Decision**: A non-zero subprocess exit (e.g. `claude` not on PATH → `TranscribeError`, exit 2)
makes `classify` raise (propagating the subprocess's stderr message) and **stop the run** — no
fallback to `--backend api`. The CLI dispatch surfaces the message and exits non-zero.

**Rationale**: FR-006 / SC-003 — a missing prerequisite is the operator's to fix; a silent
half-empty run is worse. Exit 2 (config) is distinct from exit 0 + `parse_errors` (per-page).

## R4. Injectable transcriber seam (testability)

**Decision**: `classify_period(...)` takes a `transcribe_page` callable parameter (default: the real
subprocess runner) with signature `transcribe_page(read_path) -> dict | "{fields..}"` returning the
typed `fields` object, or raising a `ClassifyConfigError` for a config error. Unit tests inject a
fake that returns canned typed fields / raises, so no real subprocess or model runs. The per-page
error path is signalled either by the fake returning an `{"error": ...}` sentinel or by the runner
detecting `parse_errors` — the loop normalizes both to an error row.

**Rationale**: Mirrors the existing `build_attachment_analysis(..., provider)` injection seam and the
`validate_page_fields(typed_validator=...)` injection — established pattern in this codebase for
keeping the deterministic core unit-testable without I/O. FR-015 requires exactly this coverage.

**Alternatives considered**:
- *`unittest.mock.patch` the subprocess* — usable but the explicit callable seam is cleaner and the
  repo's convention (per `CLAUDE.md` test-coverage note: "tests drive the pure seams … the injected
  `provider`").

## R5. Tightening the gate to typed-only + deleting flat code

**Decision**: In `validate_page_fields`, after the `{"error": ...}` branch, **require** a typed
payload: a dict carrying a valid `doc_type` (schema-validated via the injected `typed_validator`).
Any payload that is neither `{"error": ...}` nor typed is rejected with a clear message. Delete the
flat branch and the `REQUIRED_KEYS` / `PAPEL_VALUES` / `STRING_OR_NULL` / `AMOUNT_KEYS` constants and
the `is_typed` predicate (no longer needed — typed is the only fields shape). In
`type_mappers.to_reconciliation_fields`, delete the `_passthrough_flat` branch (a dict without
`doc_type` now falls through to `_canonical_doc_type(...) → outro` mapper, or we keep a defensive
empty fallback). In the UI, remove `isTyped` and always use the typed flatten (`typed-transcription`
builder), with the existing defensive try/catch retained as the degradation path.

**Rationale**: FR-008/FR-009. The DB is wiped (no flat rows), and after the skills are gone no
producer emits flat, so the flat code is provably dead. Keeping one contract removes the whole
"which shape" branch class.

**Care points**:
- `record_classification`'s `is_error = "error" in payload` check stays (independent of `is_typed`).
- `to_reconciliation_fields` must still never raise on a non-dict / malformed input (keep the
  `_empty()` fallback for `None`/non-dict). A dict lacking `doc_type` is now an unexpected shape;
  route it to `_map_outro` (best-effort) rather than re-introducing flat tolerance — but since the
  gate rejects such payloads at write time, this is only a defensive read-path fallback.

## R6. Corrections gate injection (FR-010)

**Decision**: `reclassify` and `apply_correction` currently call `validate_page_fields(fields)` and
`record_classification(..., fields)` **without** a `typed_validator`. To satisfy FR-010 end-to-end
(typed payloads schema-validated through the same gate the CLI enforces), inject
`typed_gate.validate_typed` at those call sites. Import it lazily inside `corrections.py` (matching
the `record-classification` CLI dispatch and the lazy-import convention) so `corrections.py` does not
import `tools/` at module load.

**Rationale**: After tightening, a flat corrected page would be rejected; the `fix-document-findings`
agent already builds the page's existing (typed) shape, so injecting the validator makes the
correction path enforce the same typed schema as `record-classification`, closing the gate
consistently. Without injection, a typed payload is only structurally checked (dict + has
`doc_type`), which is weaker than the CLI path.

**Alternatives considered**:
- *Leave corrections structurally-only* — acceptable for "passes the gate" but inconsistent with the
  `record-classification` guarantee; injecting the validator is the small, correct closure.

## R7. Docs / agents / skills to update or delete

- **Delete**: `.claude/skills/classify-doc-page/` (incl. `scripts/validate_image.py`),
  `.claude/skills/classify-period/`, `.claude/agents/analyze-docs.md`.
- **Rewire**: `.claude/skills/improve-classification/SKILL.md` → run `classify → apply-extractions →
  analyze → mismatches` as plain bash (it runs in the main context and previously delegated to the
  `analyze-docs` agent).
- **Update references**: `.claude/agents/fix-mismatch.md` (its "reading" target is now the
  `doc_transcribe` prompt/schemas), `.claude/agents/review-mismatch.md` (descriptive `analyze-docs`
  reference).
- **Docs**: `docs/pipeline.md`, `scripts/pipeline-flow.md`, `scripts/README.md`,
  `docs/runbooks/fix-document-vision-mismatch.md`, `CLAUDE.md` (the long "Attachment analysis (Claude
  vision skills)" pattern paragraph) — describe the all-CLI typed `classify` flow.
- **`docs/features/false-positive-triage-agent.md`** mentions `classify-period` only descriptively;
  update if it references it as a live dependency (it is a design doc — adjust the line, do not
  redesign).

**Note**: `agnostic`/skill-defs cache per session (project memory) — editing a SKILL.md mid-session
won't reload, but that does not matter here since these are deletions/rewrites shipped in a PR.
