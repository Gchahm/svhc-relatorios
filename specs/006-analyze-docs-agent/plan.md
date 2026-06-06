# Implementation Plan: Claude Vision Agent for Document Analysis (retire the VLM flow)

**Branch**: `006-analyze-docs-agent` | **Date**: 2026-06-06 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/006-analyze-docs-agent/spec.md`

## Summary

Replace only the per-page image→structured-fields extraction step of the document-analysis stage
(currently `mlx_vlm` / Qwen2.5-VL in `scripts/scraper/analise/documentos.py`) with a Claude vision
**subagent**. The agent reads each relevant page image and writes a per-page **extractions file**;
a deterministic, model-free pipeline then consumes that file and runs the existing NF grouping,
heterogeneity-aware roll-up, group reconciliation, sibling fan-out, entry validation, and JSON
write-back — producing `document_analyses` rows byte-shape-identical to today, so
`scripts/import-to-d1.mjs` and the `duplicate_billing` check are unaffected. The work is split into
three deterministic touchpoints around the agent: **plan** (select + group documents into a work
manifest), **agent** (vision extraction → extractions file), **apply** (manifest + extractions →
period JSON). The `mlx_vlm` model-load and inference code and the dependency are then removed.

## Technical Context

**Language/Version**: Python 3.11+ (scraper/analysis pipeline under `scripts/scraper/`); Markdown
agent definition under `.claude/agents/` (Claude Code subagent, like `pm.md`)
**Primary Dependencies**: Python stdlib only (`json`, `pathlib`, `hashlib`, `re`, `argparse`).
**Removes** the `mlx_vlm` dependency. The agent uses the Claude Code Read tool's native image
vision — no new runtime library.
**Storage**: Period JSON files under `data/scrape/<YYYY-MM>.json` (source of truth). Two new
working artifacts alongside them: `<period>.extract-todo.json` (work manifest) and
`<period>.extractions.json` (agent output). Cloudflare D1 downstream via
`scripts/import-to-d1.mjs` (unchanged; no schema migration).
**Testing**: No framework configured (constitution Principle III — tests OPTIONAL). Verification is
a manual synthetic-extraction harness documented in `quickstart.md`: feed fixed per-page values
through the deterministic pipeline and diff the resulting `document_analyses` against expectations.
This is required because the VLM is not runnable in the dev sandbox (Apple-Silicon only).
**Target Platform**: Local developer machine / CI running Python; the vision step runs inside a
Claude Code session (any OS). No Apple-Silicon dependency after this change.
**Project Type**: Single project — Python analysis pipeline + a Claude Code agent definition.
**Performance Goals**: Shared-NF pages extracted once per unique NF (no redundant vision passes);
no hard latency target — vision pace is acceptable for batch analysis of a period.
**Constraints**: Output JSON for `document_analyses` / `document_analysis_records` MUST remain
shape-compatible with `scripts/import-to-d1.mjs`; no D1 schema change; deterministic record ids
(`det_id`) preserved so ids are stable across runs.
**Scale/Scope**: ~130 documents per period; small multi-page documents (a few pages each). One
condominium's monthly fiscal records.

## Constitution Check

_GATE: Must pass before Phase 0 research. Re-check after Phase 1 design._

- **I. Type Safety & Schema Discipline** — PASS. No TypeScript or Drizzle schema change; the D1
  table shapes (`document_analyses`, `document_analysis_records`) are preserved exactly (FR-003,
  FR-008), so no migration. `src/db/auth.schema.ts` untouched.
- **II. Cloudflare-Native Architecture** — PASS / N/A. This is the offline Python ingestion
  pipeline; it does not touch `getDb()`, Workers bindings, or runtime context.
- **III. Quality Gates Before Commit** — PASS. `pnpm lint` + `pnpm format` run before commit
  (Prettier formats the touched Markdown; no TS changes). Tests remain OPTIONAL; this feature adds
  a documented manual verification instead of a new framework (justified by SC-002 and the
  no-sandbox-VLM constraint).
- **IV. Security & Auth by Default** — PASS. No new routes, no secrets; the agent only reads local
  page images already on disk.
- **V. Simplicity & Incremental Delivery** — PASS. Reuses every existing deterministic helper;
  **removes** a dependency (`mlx_vlm`); the only new surface is two small CLI subcommands, one
  extraction-provider seam, and two working-file formats — each justified by the extraction swap.
  Delivered as prioritized, independently testable slices (P1 extraction+merge, P1 behavior
  preservation, P2 removal).

**Result**: No violations. Complexity Tracking left empty.

## Project Structure

### Documentation (this feature)

```text
specs/006-analyze-docs-agent/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/           # Phase 1 output (file-format + agent-interface contracts)
│   ├── extract-todo.schema.md
│   ├── extractions.schema.md
│   ├── page-extraction-fields.md
│   └── agent-interface.md
├── checklists/
│   └── requirements.md  # created during specify
└── tasks.md             # Phase 2 output (speckit tasks — not created here)
```

### Source Code (repository root)

```text
.claude/agents/
└── analyze-docs.md            # NEW — Claude vision subagent (replaces VLM extraction)

scripts/scraper/
├── __main__.py                # MODIFIED — replace `analyze-docs` (VLM) with `docs-plan`
│                              #   + `apply-extractions`; update interactive menu
└── analise/
    ├── documentos.py          # MODIFIED — remove _load_model/_analyze_page/mlx imports/
    │                          #   EXTRACT_PROMPT; refactor selection into select_work();
    │                          #   add provider seam; keep ALL deterministic helpers
    ├── extractions.py         # NEW — manifest + extractions file IO, FileExtractionProvider,
    │                          #   plan_extractions(), apply_extractions()
    ├── nf_groups.py           # UNCHANGED — grouping + reconcile_group
    ├── loader.py              # UNCHANGED — load_all_periods (used by plan)
    └── checks/advanced.py     # UNCHANGED — duplicate_billing reads persisted document_analyses

scripts/                       # MODIFIED (deps) — drop mlx_vlm from the Python dep manifest
                               #   (pyproject/requirements under scripts/)
CLAUDE.md                      # MODIFIED — document the agent + plan/apply flow; drop VLM refs
```

**Structure Decision**: Single-project layout. The change is localized to the Python analysis
pipeline (`scripts/scraper/analise/`) plus one new Claude agent definition and documentation. No
web/mobile split. The extraction-provider seam isolates the one swapped step from the large body of
preserved deterministic logic.

## Architecture (the three touchpoints + the agent)

1. **`docs-plan`** (deterministic, `extractions.plan_extractions`): loads periods via
   `load_all_periods`, reuses the exact selection logic factored out of `run_document_analysis`
   (`select_work`: group by NF content hash, apply min-amount/limit/id filters, skip already-analyzed
   unless reanalyze/targeted, compute per-group sibling sum + size, resolve vendor names). Picks one
   **representative** document per group and emits `<period>.extract-todo.json` carrying, per group:
   the representative's page list (with both the original `path` and an absolute `read_path` for the
   agent's Read tool) and the full member list (document_id, entry_id, entry_amount, vendor_name).
2. **`analyze-docs` agent** (`.claude/agents/analyze-docs.md`): reads the todo manifest, opens each
   representative page image with the Read tool's native vision, extracts the structured fields using
   the frozen field set, and writes `<period>.extractions.json` keyed by page `path`. Records a
   per-page `error` instead of fabricating values when a page is missing/unreadable/illegible.
3. **`apply-extractions`** (deterministic, `extractions.apply_extractions`): loads the manifest +
   extractions, rebuilds `PageAnalysisRecord`s for each representative via a `FileExtractionProvider`
   (calling the preserved `_map_artifact_role`, `_rollup_document_fields`), reconciles each group
   (`_apply_group_amount_match` / `reconcile_group`), fans out to siblings (`_fanout_result`),
   validates against entries, and writes `document_analyses` with `_merge_and_write`. Prints the same
   summary as today. The `duplicate_billing` check then runs unchanged over the persisted results.

`select_work` is the single source of truth for "what to analyze", shared by plan; apply is driven
entirely by the manifest + extractions (no re-selection) so the two steps cannot drift.

## Complexity Tracking

> No constitution violations — no entries required.

| Violation | Why Needed | Simpler Alternative Rejected Because |
| --------- | ---------- | ------------------------------------ |
| (none)    | —          | —                                    |
