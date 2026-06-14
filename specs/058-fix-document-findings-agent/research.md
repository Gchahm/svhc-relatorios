# Phase 0 Research: fix-document-findings agent + reclassify CLI

All "unknowns" here are *placement / reuse* decisions, not external technology choices — the heavy
primitives already exist (TRIAGE-001/002/003). Each decision below resolves a NEEDS-CLARIFICATION-class
question about how the new agent + CLI sit on top of the existing code.

## Decision 1 — Where does `reclassify()` live, and how does it reuse the propagation ordering?

**Decision**: Implement `reclassify()` in `scripts/analysis/corrections.py` (alongside `apply_correction`),
and factor the propagation ordering into a small shared helper there. The composite CLI `reclassify`
command (in `__main__.py`) calls it.

**Rationale**:
- `corrections.py` already imports `apply_extractions` (from `extractions`) and lazily imports
  `run_analysis` (from the package `__init__`), and already owns the exact `_propagate` ordering
  (`clear_classified_stamp` → staging-driven `apply_extractions` → `run_analysis`, which rebuilds
  `build-documents` + writes alerts), plus `_attachment_context` (period resolution) and `_q` (escaping).
  Putting `reclassify` here means **zero new import wiring and zero duplicated ordering**.
- `extractions.py` is imported *by* `corrections.py`; defining `reclassify` in `extractions` and having it
  call the propagation pipeline would invert that dependency or duplicate the `run_analysis` lazy import.
  Keeping the un-gated `reclassify` next to the gated `apply_correction` keeps the two siblings together
  (one with the audit/verify net, one without) and reuses the same helpers.

**Alternatives considered**:
- *A new module `reclassify.py`*: rejected — it would re-import the same pipeline and re-implement period
  resolution + escaping; no benefit over co-locating with `corrections`.
- *Put it in `extractions.py` (where `apply_extractions` lives)*: rejected — creates an import cycle or
  duplication with `run_analysis`/`_propagate`, which live above `extractions`.

**Shared helper**: extract the body of `corrections._propagate` is already the exact ordering needed; keep
`_propagate` as the single propagation function and have `reclassify` call it after recording staging.
`_attachment_context` (period) is reused as-is. No public-surface churn in other modules.

## Decision 2 — `reclassify` validation + payload contract

**Decision**: Validate each supplied page payload with the existing `validate_page_fields` gate (the same
one `record-classification` and `apply-correction` use), reject (exit 1, write nothing) on any failure,
record each page via `record_classification`, then `_propagate`. Accept `--pages` as a JSON string or via
stdin (`-`/omitted), mirroring `apply-correction`'s `__main__` handling exactly. Print a terse JSON result
to stdout; the propagation banner is routed to stderr by `_propagate`'s existing `redirect_stdout`.

**Rationale**: Reuses the established contract gate and CLI idiom (FR-014, FR-016) — no new validation path,
no drift, parseable stdout. An empty `corrected_pages` is a no-op (nothing recorded, nothing propagated).

**Alternatives considered**:
- *A new lighter validation*: rejected — would diverge from the `record-classification` contract the
  staging table enforces; the typed/flat dual-path gate (feature 055) is exactly what `validate_page_fields`
  already routes.

## Decision 3 — `reclassify` vs `apply-correction`: when does the agent use which?

**Decision**: The agent uses **`apply-correction`** for every autonomous data change (it is audited,
verify-after-gated, and reversible — load-bearing under full autonomy, design D3/§7). `reclassify` is the
**un-gated ordering primitive** (design §4.5) — exposed for humans / future tooling that want a propagation
without the audit/verify gate (e.g. re-running a known-good page set). The agent prompt directs all
corrections through `apply-correction`; it does NOT call `reclassify` for autonomous corrections (that would
bypass the safety net).

**Rationale**: §4.5 explicitly frames `reclassify` as ergonomics, not the audited path: "With staging-driven
`apply` (4.1+4.2), a mid-sequence crash is already non-destructive … so this is purely ergonomic, not a
safety requirement." The audited path the autonomous agent must use is `apply-correction`.

**Alternatives considered**:
- *Agent calls `reclassify` then logs separately*: rejected — splits the atomic record+verify+audit that
  `apply-correction` already provides and risks an unaudited prod write.

## Decision 4 — Agent judgment taxonomy + result buckets

**Decision**: The agent judges each finding into four buckets (mirroring `review-mismatch` plus a
data-correction split): `true`, `false-misread`, `systematic-fault`, `page-error`. It maps outcomes to the
result JSON:
- `false-misread` → call `apply-correction`; if `result == applied` → `corrections`; any other result
  (`rolled-back`/`flagged`/`unverifiable`/`no-op`) → `left_as_finding` (still open).
- `true` / `page-error` → `left_as_finding` (never touched).
- `systematic-fault` → `escalated` with `{area, hypothesis}` (no data change).

**Rationale**: Aligns the established `review-mismatch` verdict vocabulary (`true`/`false`/`transient`/
`page-error`) with the design §5 three-branch decision tree (leave / data-correct / escalate). The
`apply-correction` result codes (`applied`/`rolled-back`/`flagged`/`unverifiable`/`no-op`) are authoritative
for whether a correction actually cleared the finding (FR-009), so the agent trusts them rather than
re-judging.

**Alternatives considered**:
- *Reuse `review-mismatch`'s 4-verdict set verbatim* (`transient` instead of `systematic-fault`): rejected —
  `transient` (an incidental misread a re-run fixes) is, for this agent, just a `false-misread` it should
  correct; the meaningful new axis is *isolated misread vs systematic fault* (design §5), so the taxonomy
  names that.

## Decision 5 — `target_finding` key the agent passes to `apply-correction`

**Decision**: The agent passes the finding's **`mismatch_key`** (computed exactly as
`analysis.verdicts.mismatch_key`: `period|kind|attachment_id|entry_id`, or `period|kind|document_id` for
`document_overpayment`) as `--target-finding`. The `document-evidence` findings carry the fields needed to
compute it; the agent constructs it deterministically (or reads it if the resolver emits it).

**Rationale**: `apply_correction` keys its BEFORE/AFTER verify-after on `mismatch_key` via the
`summarize_mismatches` + `verdicts.mismatch_key` single-source detector. Passing the same key is mandatory
for verify-after to find and confirm the cleared finding (else it fails closed as `unverifiable`).

**Alternatives considered**:
- *Pass a kind+id tuple*: rejected — `apply_correction` expects the `mismatch_key` string contract.

## Decision 6 — Testing the agent

**Decision**: The agent `.md` itself is not unit-tested (agent prompts are not executable units, and skill/
agent definitions are cached per session — memory `skill-defs-cached-per-session`). It is validated by:
(a) reviewing the prompt against the shipped CLI contracts (the `document-evidence` / `apply-correction`
input/output shapes), and (b) verifying the underlying CLI primitives end-to-end against seeded D1. The new
`reclassify` orchestration IS unit-tested (pure seam: validate + ordering + scoping, propagation mocked) and
integration-tested (real D1).

**Rationale**: Constitution III — tests are added where the spec requests and where they are meaningful. The
agent's behavior reduces to its CLI calls, which are the testable surface.
