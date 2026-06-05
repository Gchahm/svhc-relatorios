# Implementation Plan: Repository Self-Assessment & Next-Feature Recommendation

**Branch**: `001-repo-self-assessment` | **Date**: 2026-06-05 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/001-repo-self-assessment/spec.md`

## Summary

Deliver a standalone Claude Code subagent — the **PM agent** at `.claude/agents/pm.md` — that, on
demand, inventories the repository's current capabilities, measures them against the project's
fraud/forgery-detection north star, and writes a dated assessment report plus a ranked
recommendation for the next feature to build. On maintainer acceptance, the PM agent drops a
self-contained feature description into a hand-off folder for a *separate* spec-running agent to
consume. The agent is advisory: it never modifies application code, schema, or data — its only
repository writes are its report and the hand-off file.

Technical approach: a single Markdown agent-definition file (YAML frontmatter + system-prompt
body) that encodes the assessment method, the goal-reference (`docs/SCOPE-fraud-detection.md`),
the impact-to-effort ranking rule, the output formats (contracts), and the file-based hand-off
protocol. Two output directories are established with committed `README.md` anchors:
`docs/assessments/` (reports) and `specs/_handoff/` (the to-be-specified inbox).

## Technical Context

**Language/Version**: Markdown + YAML frontmatter (Claude Code subagent definition). No
application runtime code is added.
**Primary Dependencies**: Claude Code subagent system (`.claude/agents/`); the `speckit` skill as
the downstream consumer of hand-off files; repo read tools (Read/Grep/Glob/Bash).
**Storage**: Filesystem only. Reports at `docs/assessments/YYYY-MM-DD-assessment.md`; hand-off
feature descriptions at `specs/_handoff/<slug>.md`. No database, no D1, no schema changes.
**Testing**: Manual validation via `quickstart.md` (invoke the agent; verify report + hand-off
outputs; confirm `git status` shows only those files). No automated test framework — consistent
with constitution Principle III (tests OPTIONAL; none configured).
**Target Platform**: Claude Code (developer tooling), operating on this repository locally.
**Project Type**: Developer tooling / agent definition. This feature is NOT part of the deployed
Next.js/Cloudflare application; it does not ship to Workers.
**Performance Goals**: A single invocation produces a complete assessment; no runtime latency or
throughput targets apply (SC-001).
**Constraints**:
- Advisory only — MUST NOT modify app code, schema, or data (FR-007, SC-005).
- Claude Code subagents CANNOT spawn other subagents → hand-off MUST be file-based, with
  orchestration to the spec-running agent happening at the main-session/human level (FR-008,
  FR-015).
- MUST NOT surface secret values (e.g. `scripts/.env`) in reports (constitution Principle IV).
**Scale/Scope**: One agent file + two anchored output folders. The current repo it assesses spans
~13 API domains, a Drizzle fiscal schema, a Python scraper, and the fraud-detection scope doc.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

Constitution v1.0.0 (`.claude/skills/speckit/memory/constitution.md`):

| Principle | Assessment | Status |
|-----------|------------|--------|
| I. Type Safety & Schema Discipline | No TypeScript, Drizzle schema, or migrations touched. The deliverable is Markdown. | ✅ Pass (N/A) |
| II. Cloudflare-Native Architecture | No DB access, no bindings, no runtime/build code. Nothing deploys to Workers. | ✅ Pass (N/A) |
| III. Quality Gates Before Commit | Deliverables are Markdown; `pnpm lint`/`pnpm format` still run clean (no app code changed). Tests remain OPTIONAL and none are added. | ✅ Pass |
| IV. Security & Auth by Default | No routes/secrets added. NEW risk: the agent reads the repo and could echo secrets — mitigated by an explicit "never surface secret values" rule in the agent prompt. | ✅ Pass (with mitigation) |
| V. Simplicity & Incremental Delivery | Single Markdown file + two anchored folders; reuses existing speckit workflow for downstream. No new dependencies or abstractions. | ✅ Pass |

**Result**: No violations. Complexity Tracking left empty. Re-checked after Phase 1 — design adds
no app code, no dependencies, and no schema; conclusion unchanged.

## Project Structure

### Documentation (this feature)

```text
specs/001-repo-self-assessment/
├── plan.md              # This file (speckit plan command output)
├── spec.md              # Feature specification (speckit specify)
├── research.md          # Phase 0 output (speckit plan command)
├── data-model.md        # Phase 1 output (speckit plan command)
├── quickstart.md        # Phase 1 output (speckit plan command)
├── contracts/           # Phase 1 output (speckit plan command)
│   ├── assessment-report.md     # Schema/template for the dated report artifact
│   └── handoff-feature.md       # Schema/template for the hand-off feature description
├── checklists/
│   └── requirements.md  # Spec quality checklist (speckit specify)
└── tasks.md             # Phase 2 output (speckit tasks command - NOT created here)
```

### Source Code (repository root)

This feature adds developer-tooling artifacts, not application source. No `src/` changes.

```text
.claude/
└── agents/
    └── pm.md                     # NEW — the PM subagent definition (frontmatter + system prompt)

docs/
└── assessments/                  # NEW — persisted, dated assessment reports
    ├── README.md                 # NEW — explains the folder + naming convention
    └── YYYY-MM-DD-assessment.md  # (produced at runtime by the PM agent)

specs/
└── _handoff/                     # NEW — hand-off inbox consumed by the spec-running agent
    ├── README.md                 # NEW — explains the hand-off protocol
    └── <slug>.md                 # (produced at runtime when a recommendation is accepted)
```

**Structure Decision**: Tooling-only feature. The PM agent lives at `.claude/agents/pm.md` (project
scope, version-controlled). Reports go to `docs/assessments/` (alongside the existing
`docs/SCOPE-fraud-detection.md`). The hand-off inbox is `specs/_handoff/` — deliberately prefixed
with `_` so it never matches speckit's `^[0-9]{3}-` branch/spec glob and cannot collide with real
spec directories. Both runtime folders are anchored with a committed `README.md` so they exist in
git before the first run.

## Complexity Tracking

> No constitution violations. No entries required.

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| —         | —          | —                                    |
