# Research: Persist typed transcriptions + flat-row coexistence

## R1 — Where the EXTRACT-001 typed validation lives

**Decision**: A new thin module `scripts/analysis/typed_gate.py` adds the repo `tools/` dir to
`sys.path` at call time and delegates typed-payload validation to
`doc_transcribe.validate_transcription(payload, doc_type)`. `record-classification` (the runtime
contract gate) calls it; the analysis *library* (`page_classifications` core, `attachments`,
`type_mappers`) does NOT import `tools/`.

**Rationale**: The issue requires "validate the payload against the EXTRACT-001 schema" at
`record-classification`. The design (§11.6) keeps the *reusable transcriber library* free of any
`scripts/analysis` dependency and vice-versa to keep `tools/doc_transcribe` extractable — but that
protects the **library**, not the **executable**. `transcribe()` itself is meant to be imported by
callers (memory `extract002-vision-transcriber`); the record-classification CLI is exactly such a
caller. Putting the import behind a single thin gate keeps the boundary explicit and the library
import-clean. `scripts/common/d1.py` already computes `_REPO_ROOT = Path(__file__).resolve().parents[2]`,
so `_REPO_ROOT / "tools"` is the import dir; the gate mirrors that resolution (the analysis CLI runs
with `cwd=scripts/`, where `tools/` is otherwise off `sys.path`).

**Alternatives considered**:
- *Mirror the validator into `scripts/analysis`* (as `type_mappers` mirrors the registry alias map):
  rejected — the validator + the six JSON Schema files are ~600 lines; mirroring them duplicates a
  contract that would silently drift, and the issue explicitly says validate against THE EXTRACT-001
  schema (the single source), not a copy.
- *Move `record-classification` into `tools/`*: rejected — it is an analysis-pipeline command tied to
  D1 (`page_classifications`), not a portable transcriber concern.

## R2 — How the typed JSON survives into the records table

**Decision**: In `build_attachment_analysis`, stop the line `record.response =
to_reconciliation_fields(parsed)` (which collapses the per-page response to the flat dict and discards
the typed JSON). Instead store the raw response (`record.response = parsed`) and derive the
reconciliation fields **at each roll-up read site** via `to_reconciliation_fields`. Concretely: the
roll-up reads (`_rollup_attachment_fields`, `_map_artifact_role`, `_pick_*`, `_sum_distinct_invoices`,
`_attachment_in_period`) operate on a *mapped view* of each record's response, while the persisted
`record.response` keeps the raw (typed or flat) JSON.

**Rationale**: FR-003 requires the rich typed JSON in `attachment_analysis_records.response`. The
records table is written from `record.response` by `d1.upsert_tables`. The mapper is already idempotent
on flat (`to_reconciliation_fields(flat) == flat` projected), and `nf_total_for_reconciliation`
already maps at read time — so mapping at read time is the established pattern, and applying it
consistently means: typed JSON stored, correct reconciliation derived, legacy flat unchanged.

**Implementation note**: To avoid scattering `to_reconciliation_fields` calls across every helper, the
cleanest seam is to keep a *derived* reconciliation dict alongside the raw response on
`PageAnalysisRecord` (e.g. a non-persisted `recon` attribute set once when the record is built), and
point the roll-up helpers at `record.recon` while persistence reads `record.response`. The derived
dict is computed once via the mapper; the raw response is what is stored. This keeps a single mapping
call per record and leaves the roll-up logic textually unchanged except for the field it reads.

**Alternatives considered**:
- *Store the flat dict AND the typed JSON in separate columns*: rejected — needs a migration
  (violates FR-005) and the UI/records contract already is one TEXT response.
- *Keep collapsing to flat (status quo)*: rejected — discards the typed JSON, failing FR-003/FR-007.

## R3 — The typed-vs-flat predicate (single source)

**Decision**: `is_typed(resp) -> bool` = `isinstance(resp, dict) and "doc_type" in resp`, defined once
in `scripts/analysis/page_classifications.py` and reused by the gate and the roll-up. The UI mirrors
the same predicate (`"doc_type" in parsed`).

**Rationale**: FR-008 — one predicate so the store/derive/render paths cannot drift. `doc_type` is the
discriminator the EXTRACT-003 mapper already keys on; reusing it keeps the contract single.

## R4 — `schema_version` tagging

**Decision**: No new column or wrapper. The typed `fields` object already embeds `schema_version` (the
EXTRACT-001 schemas make it a required single-value enum, and the transcriber stamps the canonical
value). The gate validates the typed payload against the schema, which enforces `schema_version` is
present and correct. So a stored typed response self-declares its version; a legacy flat response has
no `schema_version` (and no `doc_type`), which is exactly the typed-vs-flat signal.

**Rationale**: FR-003 ("tagged with `schema_version`") is satisfied by the embedded field; adding a
separate tag would duplicate it and risk drift. Validating against the schema guarantees the tag.

## R5 — Validation-gate behavior for the dual path

**Decision**: `validate_page_fields(payload)` (the existing canonical validator) gains a typed branch:
1. an `{"error": ...}` object → unchanged (the one permitted alternative);
2. a dict with `doc_type` → typed branch: call the gate's typed validator; aggregate errors into a
   single message; reject on any error;
3. a dict without `doc_type` → the existing flat-field branch (REQUIRED_KEYS, papel/amount typing).

Because `validate_page_fields` is stdlib-only and must not import `tools/`, the typed branch is
delegated to an injectable validator (default = the gate). The CLI wires the real gate; pure unit
tests inject a fake validator. `record_classification` raises `ValueError` on rejection (CLI exits 1),
unchanged.

**Rationale**: Keeps `record-classification` the single contract gate (FR-001) and keeps the staging
module import-clean (delegation seam), matching how `build_attachment_analysis` already takes an
injected `provider`.

## R6 — UI dual-path render

**Decision**: In `AttachmentAnalysisDetailDialog.tsx`, after parsing the stored response:
- if `"doc_type" in parsed` (typed): derive the known reconciliation fields for the summary grid from
  the typed JSON (a small mirror of the per-type mapping, OR — simpler — display the rolled-up
  attachment-level fields already shown elsewhere) AND render the full typed JSON as a readable tree
  via the existing generic key/value fallback (the component already renders unknown keys).
- else (flat): unchanged.

**Rationale**: FR-007 — both render without error. The component already iterates known + extra keys;
a typed object's nested values stringify via the existing `formatValue` (objects → `JSON.stringify`).
The minimal, low-risk change is: detect typed, and for typed records render the full transcription
(every top-level field, nested blocks expanded) rather than only the flat KNOWN_FIELDS — so the
reviewer sees the rich evidence. The flat path is left byte-identical.

## Summary of decisions

| # | Decision |
|---|----------|
| R1 | Typed validation via a thin `typed_gate.py` that adds `tools/` to `sys.path`; library stays import-clean |
| R2 | Persist raw response; derive reconciliation via the mapper at build time (a `recon` view on the record) |
| R3 | `is_typed(resp)` = `dict and "doc_type" in resp`, one source, mirrored in UI |
| R4 | `schema_version` is the embedded, schema-enforced field; no new column |
| R5 | `validate_page_fields` dual-path with an injectable typed validator (default = gate) |
| R6 | UI renders typed records richly (full transcription); flat records unchanged |
