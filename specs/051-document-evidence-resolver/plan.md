# Implementation Plan: Document→attachment(s) evidence resolver for the triage agent

**Branch**: `051-document-evidence-resolver` | **Date**: 2026-06-13 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/051-document-evidence-resolver/spec.md`

## Summary

Add a read-only `document-evidence --id <document_id>` subcommand to the `python -m analysis` CLI.
It resolves a document id to its distinct **source attachment ids** (via the `document_entries`
provenance), then delegates to the existing `summarize_mismatches(attachment_ids=...)` engine and
prints the resulting findings + `page_refs` as JSON. An unknown document id fails non-zero with a
clear message; an existing document that resolves to no source attachments prints an empty findings
result. Strictly read-only (only the existing image-materialization the summary already performs).

## Technical Context

**Language/Version**: Python 3.12 (analysis CLI under `scripts/analysis/`, run via `uv`); stdlib only.
**Primary Dependencies**: Existing only — `scripts/common/d1.py` (`wrangler`-CLI wrapper: `query`);
the existing `summarize_mismatches` engine in `scripts/analysis/extractions.py`. No new pip/npm dep.
**Storage**: Cloudflare D1 (`DATABASE` → `fiscal-db`), tables `document_entries` (read-only, for the
resolution) + everything `summarize_mismatches` already reads. **No schema change, no migration.**
Page images materialized into the ephemeral local cache `.cache/analysis/` (as `mismatches` does).
**Testing**: stdlib `unittest` under `scripts/tests/` (run `python -m unittest discover -s tests -t .`
in `scripts/`, or `pnpm test:py`). The resolution helper is a pure seam tested in isolation.
**Target Platform**: CLI invoked by the triage agent / operator; Linux dev + Cloudflare Workers data.
**Project Type**: single (Python analysis pipeline; no frontend change).
**Performance Goals**: N/A — one document, one extra `query` ahead of the existing summary.
**Constraints**: Strictly read-only (FR-004). Output JSON to stdout, matching `mismatches`.
**Scale/Scope**: One small new subcommand + one pure resolver helper + unit test. No UI, no schema.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- **I. Type Safety & Schema Discipline**: No TypeScript change; no D1 schema change ⇒ no migration.
  Python type hints used on the new function signatures. PASS.
- **II. Cloudflare-Native Architecture**: All D1 access goes through `scripts/common/d1.py` (the
  `wrangler`-CLI wrapper) with the standard `target` (local/remote) selection — no hardcoded
  endpoints. PASS.
- **III. Quality Gates Before Commit**: `pnpm lint`/`pnpm format` run before commit; Prettier covers
  the touched markdown. A stdlib `unittest` is added for the pure resolver seam (consistent with the
  existing Python test surface; the repo runs `pnpm test:py`). PASS.
- **IV. Security & Auth by Default**: CLI-only, read-only; no new endpoint, no public surface. PASS.
- **V. (mirror-table invariant)**: The command issues **zero writes** — it never touches the mirror
  tables (or any table). It only reads `document_entries` and reuses the read-only summary. PASS.

No violations — Complexity Tracking is empty.

## Project Structure

### Documentation (this feature)

```text
specs/051-document-evidence-resolver/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/           # Phase 1 output (CLI contract)
└── tasks.md             # Phase 2 output (speckit tasks)
```

### Source Code (repository root)

```text
scripts/
├── analysis/
│   ├── __main__.py      # add the `document-evidence` subparser + dispatch (edit)
│   ├── documents.py     # add `resolve_document_attachment_ids(...)` + `document_evidence(...)` (edit)
│   └── extractions.py   # `summarize_mismatches(...)` reused unchanged (no edit)
└── tests/
    └── test_document_evidence.py   # unit test for the resolver seam (new)
```

**Structure Decision**: Single Python analysis pipeline. The resolution logic lives in
`scripts/analysis/documents.py` (the module that owns the `documents` / `document_entries` entity),
keeping the document concern co-located. `__main__.py` gains a thin subparser that calls it and
prints JSON. The actual finding engine (`summarize_mismatches`) is reused untouched, so finding
shape and `page_refs` cannot drift.

## Complexity Tracking

> No constitution violations — section intentionally empty.
