# Implementation Plan: fix-document-findings agent (per-document autonomous false-positive correction)

**Branch**: `058-fix-document-findings-agent` | **Date**: 2026-06-14 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/058-fix-document-findings-agent/spec.md`

## Summary

Ship the **TRIAGE-004** per-document correction worker: (1) a context-isolated agent definition
`.claude/agents/fix-document-findings.md` that takes one document/attachment id, gathers findings via
the existing `document-evidence` resolver, views the page image(s) in its OWN context, judges each
finding (true / false-misread / systematic-fault / page-error), autonomously data-corrects only
demonstrable misreads via the existing `apply-correction` primitive (which records, applies, and
verify-after-gates each correction), and returns a terse JSON result; and (2) a thin composite
`reclassify --attachment-id --pages <json>` CLI command in `scripts/analysis` that pins the
record-staging → staging-driven `apply-extractions` → `build-documents` → `analyze` ordering (design
§4.5), reusing the `_propagate` helper already implemented for `apply-correction`.

The technical approach is **maximal reuse, minimal new code**: every heavy primitive (the resolver,
the audited correction with rollback, the propagation pipeline) already shipped in TRIAGE-001/002/003.
This feature adds an agent prompt (no code) and one small CLI command that exposes the existing
`record_classification` + `_propagate` ordering as a single un-gated entrypoint.

## Technical Context

**Language/Version**: Python 3 (stdlib-only `analysis` package — CLAUDE.md invariant); the agent is a
Markdown prompt with YAML frontmatter (no code).
**Primary Dependencies**: existing `scripts/analysis` package (`corrections.apply_correction`,
`documents.document_evidence`, `extractions.apply_extractions`, `page_classifications.record_classification`,
`common.d1`); the Claude Code agent runtime (Bash, Read, Glob tools). No new third-party dependency.
**Storage**: Cloudflare D1 via `common.d1` (`page_classifications`, `attachment_analyses`, `documents`,
`alerts`, `data_corrections`). No schema change, no migration (reuses TRIAGE-003 store).
**Testing**: stdlib `unittest` under `scripts/tests/` for the pure seam of the new `reclassify` orchestration
(period resolution + payload validation + propagation ordering, mocking the D1/propagation side effects),
plus a real-D1 integration test under `scripts/integration_tests/` (`pnpm test:py:integration`) exercising
`reclassify` against seeded Miniflare D1. The agent prompt is reviewed against the shipped CLI contracts
(agent `.md` files are not unit-testable; they are exercised via their CLI primitives — A6).
**Target Platform**: Local Miniflare D1/R2 dev + Cloudflare Workers prod; CLI invoked as
`python -m analysis …` from `scripts/`.
**Project Type**: single (Python analysis CLI + an agent definition under `.claude/agents/`).
**Performance Goals**: N/A — a per-document correction is interactive/batch latency-tolerant.
**Constraints**: `analysis` package stays stdlib-only; default LOCAL target, `--remote` explicit; the
agent must never hide a real finding (correctness floor); the agent's page-image reads stay in its own
context (terse JSON return only).
**Scale/Scope**: one document per agent invocation; one attachment per `reclassify` call. A batch
orchestrator (TRIAGE-005) fans this out and is out of scope.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- **I. Type Safety & Schema Discipline** — PASS. No DB schema change (reuses TRIAGE-003 `data_corrections`),
  so no migration. The new `reclassify` CLI is Python in the stdlib-only `analysis` package; no TypeScript
  touched. No `any`, no auth schema change.
- **II. Cloudflare-Native Architecture** — PASS. All D1 access goes through `common.d1` (the established
  `wrangler`-CLI wrapper); no direct connections. No new binding.
- **III. Quality Gates Before Commit** — PASS. Will run `pnpm lint`/`pnpm format` (prettier covers the agent
  `.md` + any markdown) and `pnpm test:py` / `pnpm test:py:integration` before the PR. The spec explicitly
  requests tests for the new CLI seam, so they are added and must pass.
- **IV. Security & Auth by Default** — PASS. No new route, no user data exposure. The agent corrects fiscal
  data autonomously, but the safety net (audit trail + reversibility + verify-after) is the TRIAGE-003
  store it reuses; `--remote` is explicit so a prod write is never implicit.
- **V. Simplicity & Incremental Delivery** — PASS. Maximal reuse: the agent is a prompt; `reclassify` is a
  thin wrapper over `record_classification` + the existing `_propagate`. No new abstraction. Shipped as one
  increment that is independently testable (the CLI) and demonstrable (the agent against seeded data).

No violations → Complexity Tracking is empty.

## Project Structure

### Documentation (this feature)

```text
specs/058-fix-document-findings-agent/
├── plan.md              # This file
├── spec.md              # Feature spec
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/           # Phase 1 output (reclassify-cli.md, fix-document-findings-agent.md)
└── tasks.md             # Phase 2 output (speckit tasks)
```

### Source Code (repository root)

```text
.claude/agents/
└── fix-document-findings.md          # NEW — the context-isolated per-document correction agent

scripts/analysis/
├── extractions.py                     # ADD reclassify() orchestration (period resolve + validate + record + propagate)
├── corrections.py                     # REUSE _propagate (extract/share the ordering if needed)
├── page_classifications.py            # REUSE validate_page_fields + record_classification
└── __main__.py                        # ADD `reclassify` subparser + handler

scripts/tests/
└── test_reclassify.py                 # NEW — pure-seam unit tests (validation, ordering, scoping; mocked propagation)

scripts/integration_tests/
└── test_reclassify_d1.py              # NEW — real-D1: record→propagate re-derives; un-staged untouched; --remote default local
```

**Structure Decision**: single-project layout. The agent lives under `.claude/agents/` next to the other
context-isolated workers (`review-mismatch`, `fix-mismatch`, `analyze-docs`). The `reclassify` command is
added to the existing `analysis` CLI (`scripts/analysis/__main__.py` + a `reclassify()` function in
`extractions.py`, the module that already owns `apply_extractions` and `document_evidence`'s sibling
`summarize_mismatches`). Tests follow the established split: pure unit tests in `scripts/tests/`, real-D1
in `scripts/integration_tests/`.

## Complexity Tracking

> No Constitution Check violations — section intentionally empty.
