# Phase 0 Research: Claude Vision Agent for Document Analysis

All three scope-defining unknowns were resolved with the maintainer during `specify` (see the
spec's Clarifications). This document records those decisions plus the supporting technical
research that grounds the plan. There are no remaining NEEDS CLARIFICATION items.

## Decision 1 — Agent boundary: extraction only

**Decision**: The Claude agent replaces **only** the per-page image→structured-fields step. NF
grouping, the heterogeneity-aware roll-up, group reconciliation, sibling fan-out, entry validation,
and JSON write-back stay in deterministic Python.

**Rationale**: That surrounding logic is tested, subtle (heterogeneity-aware amount precedence;
content-hash grouping; 5%/R$0.05 reconciliation), and depended on by the `duplicate_billing` check
and the D1 import contract. Re-deriving it inside free-form model reasoning would be fragile and
unverifiable. Isolating the single non-deterministic step keeps the change small and behavior
exactly preserved (SC-002).

**Alternatives considered**: End-to-end agent (agent computes roll-up/reconciliation and writes the
final JSON) — rejected: re-implements tested logic in prose, hard to verify, higher regression risk.

## Decision 2 — Invocation: subagent + deterministic merge

**Decision**: A `.claude/agents/analyze-docs.md` subagent (same convention as `pm.md`) writes a
per-page extractions file; a thin deterministic command merges it into the period JSON. No model or
network API call inside the Python loop.

**Rationale**: Matches the existing agent precedent in this repo, runs anywhere Claude Code runs,
and keeps the deterministic pipeline pure (no runtime API dependency, fully reproducible given an
extractions file). The intermediate file is also the natural seam for the synthetic-extraction
verification that SC-002 requires.

**Alternatives considered**:

- Headless `claude` CLI shelled out from Python per page — rejected: adds a runtime CLI/API
  dependency to the pipeline and is awkward to drive/inspect interactively.
- Both (subagent + CLI) — rejected for now (YAGNI / Principle V): more surface than the need.

## Decision 3 — VLM disposition: remove, keep deterministic helpers

**Decision**: Delete `_load_model`, `_analyze_page`, the module-level `_model/_processor` globals,
the `mlx_vlm` imports, and `EXTRACT_PROMPT` from `documentos.py`; drop the `mlx_vlm` dependency from
the Python manifest under `scripts/`. Keep every deterministic helper.

**Rationale**: The maintainer chose true retirement; the Apple-Silicon-only dependency is the whole
problem (it cannot run in the sandbox/CI — see project memory). Keeping it behind a flag would
leave the dependency in the tree and create two code paths to maintain.

**Alternatives considered**: Keep mlx behind a flag as fallback — rejected: defeats "retire", keeps
the unrunnable dependency.

## Supporting research

### R1 — What exactly is VLM-specific vs. reusable in `documentos.py`

VLM-specific (to remove): `_load_model`, `_analyze_page`, `_model`/`_processor` globals, `mlx_vlm`
imports, `EXTRACT_PROMPT`. Everything else is deterministic and reused:
`PageAnalysisRecord`, `DocAnalysisResult`, `_parse_brl_value`, `_check_date_in_period`,
`_normalize_name`, `_page_label_from_path`, `_ROLE_ALIASES`, `_map_artifact_role`,
`_rollup_document_fields`, `nf_total_for_reconciliation`, `_apply_group_amount_match`,
`_fanout_result`, `_merge_and_write`. The JSON-from-text parser `_parse_vlm_response` is retained
(renamed `_parse_json_blob`) to tolerate an agent that wraps JSON in prose/fences.

**Implication**: `analyze_single_document` is refactored to take an **extraction provider**
(`path -> (parsed: dict | None, error: str | None)`) instead of loading a model; the file-backed
provider supplies values from the extractions file.

### R2 — Selection logic is shared and must not drift

The document selection + grouping in `run_document_analysis` (content-hash groups, sibling sums,
min-amount/limit/id filters, skip-already-analyzed) is exactly the work the agent's manifest needs.
Factor it into `select_work(...)` and emit the manifest from it. **Apply is driven by the manifest
(+ extractions), not by re-running selection**, so plan and apply cannot diverge.

### R3 — Page-image path resolution for the agent's Read tool

In the period JSON, `file_path` tokens look like `../data/scrape/2025-12/<id>_p1.jpg` (relative to
`scripts/`, where the pipeline runs). The Read tool needs a path resolvable from the agent's cwd.
**Resolution**: the manifest carries, per page, both the original `path` (the extraction key, used by
the deterministic provider exactly as `content_hash`/`file_path` are read today) and an absolute
`read_path` (resolved at plan time) that the agent passes to Read. The extractions file is keyed by
`path` so the provider matches without any path-normalization guesswork.

### R4 — Frozen extraction field set (agent must match the VLM contract)

The agent must emit exactly the fields the VLM produced, since `_map_artifact_role` and
`_rollup_document_fields` consume them and the persisted shape feeds import + checks:
`papel_artefato` (invoice|nfse|boleto|payment_proof|other), `tipo_documento`, `valor_total` (gross),
`valor_liquido` (net), `valor_pago` (paid), `cnpj_emitente`, `nome_emitente`, `data_emissao`
(DD/MM/YYYY), `numero_documento`, `descricao_servico`. Amounts may be numbers or BRL strings
(`_parse_brl_value` handles both); unknown fields are `null`. This set is frozen in
`contracts/page-extraction-fields.md` and mirrored verbatim in the agent prompt.

### R5 — Determinism and record ids

`det_id("doc_analysis", document_id)` and the per-record id derive from document identity and
analysis type/page — **not** from extracted values. So even though vision values may vary slightly
run-to-run, the JSON ids stay stable and `_merge_and_write` keeps replacing prior analysis for the
same document cleanly. This satisfies the "non-determinism acceptable, ids stable" edge case.

### R6 — Verification without a VLM (sandbox constraint)

The VLM cannot run in the dev sandbox (project memory: Apple-Silicon only). SC-002 is verified by
the synthetic-extraction harness: hand-author an `<period>.extractions.json` with known values for a
few documents (including a shared-NF group and a heterogeneous document), run `apply-extractions`,
and assert the resulting `document_analyses`, reconciliation classifications, and `duplicate_billing`
alerts match expectations. This exercises 100% of the changed deterministic path with no model.
