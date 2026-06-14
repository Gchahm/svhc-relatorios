# Implementation Plan: triage-false-positives skill (batch orchestrator over open findings)

**Branch**: `059-triage-false-positives` | **Date**: 2026-06-14 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/059-triage-false-positives/spec.md`

## Summary

A thin batch orchestrator **skill** (`.claude/skills/triage-false-positives/SKILL.md`) that, given a
period and an optional finding filter, lists the period's candidate documents **read-only** via the
existing `mismatches` CLI, fans out **one `fix-document-findings` agent per distinct candidate** (in
parallel, budget-isolated), collects each agent's terse JSON result, and prints a single aggregated
summary (corrected N / left M findings by reason / escalated K systematic faults). It is pure
coordination: it holds no page images, runs no corrections itself, and changes no code/schema/data.
It mirrors the existing `improve-classification` orchestrator skill in shape (delegation-only,
main-context, reads back terse JSON).

## Technical Context

**Language/Version**: Markdown skill prompt (`SKILL.md`); composed CLI is Python 3 under `scripts/`
(invoked, not modified). No application code change.
**Primary Dependencies**: existing `python -m analysis mismatches` CLI (read-only listing) and the
existing `fix-document-findings` agent (`.claude/agents/fix-document-findings.md`, merged via #92).
**Storage**: none added. Reads D1/R2 only indirectly through the composed CLI/agent.
**Testing**: No automated test framework for skills/agents in this repo (constitution III — tests
OPTIONAL). Verification is a live run of the skill against the local seeded/real period (quickstart).
The composed assets already carry their own unit + integration tests.
**Target Platform**: Claude Code agent harness (skill runs in the main context; agents are spawned via
the Task tool).
**Project Type**: single (orchestrator skill prompt) — no `src/` change.
**Performance Goals**: N/A — fan-out is bounded by the candidate count; each agent is budget-isolated.
**Constraints**: the orchestrator MUST open zero page images in its own context (SC-002); one bad
agent MUST NOT abort the batch (FR-008).
**Scale/Scope**: a single SKILL.md (~one screen of prompt), plus this spec set. No CLI/schema/UI files.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- **I. Type Safety & Schema Discipline** — N/A. No TypeScript, no Drizzle schema, no migration. PASS.
- **II. Cloudflare-Native Architecture** — N/A. No DB access added; the composed CLI already routes
  all D1/R2 through `scripts/common/d1.py`. PASS.
- **III. Quality Gates Before Commit** — `prettier --check .` covers markdown (CI gate, project
  memory). The new `SKILL.md` + spec markdown MUST be Prettier-clean before push. No code → no
  `pnpm lint` impact, but it will be run. Tests OPTIONAL and none are added (skill prompt). PASS.
- **IV. Security & Auth by Default** — N/A. No new route or data exposure; the skill only spawns
  agents that use already-gated CLIs. `--remote` is explicit-only (never writes prod implicitly,
  FR-011). PASS.
- **V. Simplicity & Incremental Delivery** — the skill is the minimal composition of two existing
  assets; no new CLI command, agent, abstraction, or dependency (Assumptions). It reuses the
  `improve-classification` orchestrator pattern verbatim. PASS.

No deviations. Complexity Tracking empty.

## Project Structure

### Documentation (this feature)

```text
specs/059-triage-false-positives/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/           # Phase 1 output (the skill I/O contract)
├── checklists/
│   └── requirements.md  # spec quality checklist
└── tasks.md             # Phase 2 output (speckit tasks)
```

### Source Code (repository root)

```text
.claude/skills/triage-false-positives/
└── SKILL.md             # THE deliverable — the orchestrator prompt (frontmatter + procedure)
```

No other files change. (The composed `mismatches` CLI and `fix-document-findings` agent already
exist and are NOT modified.)

**Structure Decision**: Single deliverable file — a skill prompt, mirroring the sibling
`improve-classification/SKILL.md` (also a single-file delegation-only orchestrator). No `references/`
folder is needed (the procedure fits in one file; `improve-classification` likewise has none).

## Complexity Tracking

None. No constitutional deviation; no new abstraction or dependency.
