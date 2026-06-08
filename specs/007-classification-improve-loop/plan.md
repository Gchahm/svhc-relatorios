# Implementation Plan: Self-Improving Document-Classification Loop

**Branch**: `007-classification-improve-loop` | **Date**: 2026-06-08 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/007-classification-improve-loop/spec.md`

## Summary

Build the rest of the self-improving classification loop on top of the already-shipped vision step
(US1 / the `analyze-docs` agent). Two new pieces of judgment + coordination land in this branch:

- **US2 — Review.** A new context-isolated **`review-mismatch` agent** (Claude-vision) looks at one
  mismatch's page image(s) + ledger entry and emits a terse **verdict** (`true | false | transient |
  page-error`), with a root-cause hypothesis for `false`. Verdicts are persisted as a per-period JSON
  working file via a new deterministic CLI (`record-verdict`), not in D1.
- **US3 — Orchestrator loop.** A thin **`/improve-classification` orchestrator skill** (run in the
  main context so it can delegate to subagents) repeats: `analyze-docs` → review each mismatch →
  for each `false`, delegate a **`fix-mismatch` worker** that runs the speckit pipeline on a branch
  and **opens a PR (never merges)** → re-run `analyze-docs` **scoped to affected documents** → until
  convergence or a stop condition. All loop bookkeeping (open mismatches, iteration count,
  stop-condition signals, which docs to re-scope) is computed by a deterministic `loop-state` CLI so
  the result is reproducible and the orchestrator holds almost no state.

**Technical approach:** keep vision/judgment in thin, context-isolated Claude agents and keep every
file-IO / accounting / stop-condition decision in stdlib Python under `scripts/analysis/`. No
TypeScript, no Cloudflare/D1 schema change — this feature lives entirely in `.claude/agents/`,
`.claude/skills/`, and `scripts/analysis/`, with working artifacts under `data/scrape/`.

## Technical Context

**Language/Version**: Python 3.12 (stdlib only) for the analysis CLI under `scripts/` (managed by
`uv`); Markdown agent/skill definitions for the Claude Code workers. No TypeScript/React changes.
**Primary Dependencies**: Claude Code Agent + Skill + Read/Glob/Bash tooling; the existing
`python -m analysis` CLI (`docs-plan`/`apply-extractions`/`analyze`/`mismatches`); the existing
`analyze-docs` agent and `classify-period`/`classify-doc-page` skills; the `speckit` skill and `gh`
CLI (used only by the fix worker). No new third-party Python packages.
**Storage**: per-period JSON working files alongside the period data — `data/scrape/<period>.verdicts.json`
(verdicts + loop state). Source of truth remains `data/scrape/<period>.json`; mismatches/alerts come
from the existing `document_analyses` + `alerts`. **No D1 schema change.**
**Testing**: none configured (repo has no test framework — Constitution III); the deterministic
`record-verdict`/`loop-state` helpers are written to be hand-verifiable and are exercised via the
quickstart. Optional manual verification per the quickstart.
**Target Platform**: developer / maintainer workstation running Claude Code against the repo (the
analysis pipeline and the loop run locally, not in the deployed Worker).
**Project Type**: single project — analysis pipeline (Python) + Claude agents/skills. Not a web
feature; the Next.js app is untouched.
**Performance Goals**: a subset re-run cost is ~proportional to the subset size (SC-001/SC-006); the
orchestrator's context does not grow with document/page volume (SC-002).
**Constraints**: vision/judgment must reuse existing skills (FR-001); no parallel extractor; every
heavy step runs in an isolated worker that returns only terse text; fixes are human-gated (never
auto-merged, FR-008/SC-005); the loop must always terminate (FR-009/SC-005).
**Scale/Scope**: a scraped period is tens–low-hundreds of documents; a loop run handles the open
mismatch set (typically single digits to low tens) and caps iterations (default 3).

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

This feature touches the Python analysis pipeline and Claude agent/skill definitions, **not** the
Next.js/Cloudflare app. Most principles are about the TypeScript/D1 surface and are satisfied by not
touching it. Mapping to the five Core Principles:

- **I. Type Safety & Schema Discipline** — ✅ No Drizzle/D1 schema change (verdicts are JSON working
  files, per the spec's explicit assumption). `src/db/auth.schema.ts` untouched. The new JSON
  artifacts have a documented contract (`contracts/`) acting as their schema.
- **II. Cloudflare-Native Architecture** — ✅ Not applicable: no DB access, no runtime bindings. The
  loop runs locally over `data/scrape/` files and the existing CLI; nothing is added to the Worker
  request path.
- **III. Quality Gates Before Commit** — ✅ Python files run through the repo's existing tooling; no
  new test framework is mandated (tests remain OPTIONAL). The fix worker's *output* PRs are normal
  feature branches that themselves must pass `pnpm lint`/`pnpm format` before a human merges.
- **IV. Security & Auth by Default** — ✅ No new routes or data exposure. The fix worker uses `gh`
  with the developer's existing auth and never merges; no secrets added to source.
- **V. Simplicity & Incremental Delivery** — ✅ Reuses the existing skills/agent and CLI rather than a
  parallel implementation (FR-001); adds the *smallest* new surface (one agent, one orchestrator
  skill, one fix worker, two deterministic CLI commands, one JSON artifact). Delivered as
  independently testable slices (US2 before US3). New agents follow the established `analyze-docs` /
  `pm` agent conventions.

**Result: PASS** — no violations; Complexity Tracking left empty.

## Project Structure

### Documentation (this feature)

```text
specs/007-classification-improve-loop/
├── plan.md              # This file
├── spec.md              # Feature spec (with Clarifications)
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output (Mismatch, Verdict, FixProposal, LoopState)
├── quickstart.md        # Phase 1 output (run the loop end-to-end on one period)
├── contracts/           # Phase 1 output (worker + CLI + file contracts)
│   ├── review-mismatch.agent.md      # review worker interface (input mismatch → verdict)
│   ├── verdicts-file.schema.md       # <period>.verdicts.json shape (verdicts + loop state)
│   ├── verdict-cli.md                # record-verdict / loop-state CLI contract
│   ├── orchestrator-loop.md          # the loop algorithm + stop conditions + scoping
│   └── fix-mismatch.worker.md        # fix worker interface (false mismatch → human-gated PR)
└── tasks.md             # Phase 2 output (speckit tasks — NOT created here)
```

### Source Code (repository root)

```text
.claude/
├── agents/
│   ├── analyze-docs.md            # EXISTING — US1 vision step (unchanged; the loop's step 1)
│   ├── review-mismatch.md         # NEW — US2 review worker (Claude-vision, context-isolated)
│   └── fix-mismatch.md            # NEW — US3 fix worker (runs speckit on a branch, opens PR)
└── skills/
    ├── classify-period/           # EXISTING — reused by analyze-docs (unchanged)
    ├── classify-doc-page/         # EXISTING — reused (unchanged)
    └── improve-classification/    # NEW — US3 thin orchestrator (runs in main context)
        └── SKILL.md

scripts/analysis/
├── __main__.py                    # CHANGED — register `record-verdict` and `loop-state` subcommands
├── extractions.py                 # EXISTING — docs-plan/apply-extractions/mismatches (unchanged)
└── verdicts.py                    # NEW — verdict persistence + deterministic loop-state/stop logic

data/scrape/
└── <period>.verdicts.json         # NEW working artifact — verdicts + loop state (no D1 schema)
```

**Structure Decision**: Single project, split along the existing seam the repo already uses —
**thin Claude workers for vision/judgment/codegen, deterministic stdlib Python for IO + accounting**.
US1 (`analyze-docs`) is reused unchanged. US2 adds the `review-mismatch` agent plus a `verdicts.py`
module (persistence) wired into the `python -m analysis` CLI. US3 adds the `improve-classification`
orchestrator skill (deliberately run in the **main** context so it can spawn the isolated workers —
a subagent cannot spawn subagents) and the `fix-mismatch` worker. Loop determinism and stop
conditions live in Python (`loop-state`) so the working set is reproducible (SC-003) and termination
is guaranteed (SC-005), independent of model variation.

## Complexity Tracking

> No Constitution Check violations — table intentionally empty.

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| — | — | — |
