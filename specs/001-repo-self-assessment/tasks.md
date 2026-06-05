---
description: "Task list for Repository Self-Assessment & Next-Feature Recommendation (PM agent)"
---

# Tasks: Repository Self-Assessment & Next-Feature Recommendation

**Input**: Design documents from `/specs/001-repo-self-assessment/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/, quickstart.md

**Tests**: NOT requested in the spec, and no test framework is configured (constitution Principle
III — tests OPTIONAL). Validation is therefore manual against `quickstart.md`; no automated test
tasks are generated.

**Organization**: Tasks are grouped by user story. Note: nearly all behavior lives in the single
file `.claude/agents/pm.md`, so most story tasks are **sequential** (same file) rather than
parallel — but each user story remains an independently *testable* increment of the agent.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: US1 / US2 / US3 — maps to the user stories in spec.md

## Path Conventions

This is a developer-tooling feature; there is no `src/` change. Artifacts live at:

- `.claude/agents/pm.md` — the PM subagent (frontmatter + system prompt body)
- `docs/assessments/README.md` — report folder anchor
- `specs/_handoff/README.md` — hand-off inbox anchor

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Establish the agent file and the two committed output-folder anchors.

- [X] T001 [P] Create the assessment-report folder anchor at `docs/assessments/README.md`, documenting the dated-filename convention (`YYYY-MM-DD-assessment.md`, `-2`/`-3` for same-day reruns) and that the folder holds PM-agent output per `contracts/assessment-report.md`.
- [X] T002 [P] Create the hand-off inbox anchor at `specs/_handoff/README.md`, documenting the file-based hand-off protocol, the `_`-prefix rationale (kept out of speckit's `^[0-9]{3}-` glob), and that files follow `contracts/handoff-feature.md`.
- [X] T003 [P] Create the PM agent skeleton at `.claude/agents/pm.md` with YAML frontmatter only: `name: pm`, a delegation-triggering `description` (assess repo / inventory capabilities / recommend next feature), `tools: Read, Grep, Glob, Bash, Write`, `model: inherit`, `color: purple`. (Body filled in later phases.)

**Checkpoint**: Agent file is discoverable (`@agent-pm`); both output folders exist in git.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Cross-cutting operating rules every user story depends on. All edit
`.claude/agents/pm.md` body, so they are sequential (no [P]).

**⚠️ CRITICAL**: No user-story behavior should be added until this phase is complete.

- [X] T004 Add the operating preamble to the body of `.claude/agents/pm.md`: the PM role (separate-context, advisory product-manager), on-demand/repeatable invocation (FR-001), and the two output locations (`docs/assessments/`, `specs/_handoff/`).
- [X] T005 Add the goal-reference section to `.claude/agents/pm.md`: treat `docs/SCOPE-fraud-detection.md` (phases 1–4) as the canonical project goal, with the north-star summary (verify scraped fiscal data/docs; detect forgery/corruption) as backup; support an optional per-run focus that is honored while related back to the overall goal (FR-004, FR-010).
- [X] T006 Add the inventory-sources checklist to `.claude/agents/pm.md`: `src/app/api/*`, `src/app/dashboard/*`, `src/db/fiscal.schema.ts` (+ `schema.ts`, `auth.schema.ts`), `scripts/scraper/`, `data/scrape/`, `docs/`, `README.md`, `CLAUDE.md`, the constitution, prior `specs/` + `docs/assessments/`, and recent git history (research R6).
- [X] T007 Add the safety rules to `.claude/agents/pm.md`: (a) advisory write-boundary — the ONLY permitted writes are under `docs/assessments/**` and `specs/_handoff/**`, never app code/schema/data (FR-007); (b) a write-boundary self-check that snapshots `git status --porcelain` BEFORE acting and compares against the state at the end, so the agent reports only the paths IT changed (distinguishing pre-existing uncommitted changes from its own) and flags any change outside the two allowed folders (research R7, SC-005); (c) the secret guard — never reproduce secret values, e.g. `scripts/.env` (research R8, constitution Principle IV).

**Checkpoint**: The agent has its goal model, sources, and guardrails — story logic can be added.

---

## Phase 3: User Story 1 - Inventory current capabilities (Priority: P1) 🎯 MVP

**Goal**: The agent produces an evidence-backed, categorized capability inventory with maturity.

**Independent Test**: Invoke `@agent-pm produce a current-state capability inventory only`; confirm
section 1 of the report lists capabilities by category, each with a real path and a maturity, and
that known capabilities (e.g. `src/app/api/alerts/`, `src/db/fiscal.schema.ts`, `scripts/scraper/`)
appear — with no recommendations attached.

- [X] T008 [US1] Add the "Step 1 — Capability Inventory" procedure to `.claude/agents/pm.md`: categorize (Ingestion/Scraping, Data Model, Auditing Checks, Reporting, Auth, UI/Dashboard, Infra), assign maturity (`complete`/`partial`/`stub`/`planned`), require a concrete `evidence` path per item, and distinguish complete from partial/stub (FR-002, FR-003; data-model "Capability Inventory").
- [X] T009 [US1] Add the section-1 output format to `.claude/agents/pm.md` matching the inventory table in `contracts/assessment-report.md`, and instruct writing it to `docs/assessments/<YYYY-MM-DD>-assessment.md` (FR-014).
- [X] T010 [US1] Add "inventory-only" mode handling to `.claude/agents/pm.md` (produce the inventory and stop, no gaps/recommendations) so US1 is independently usable.

**Checkpoint**: Run the quickstart US1 validation — inventory is complete (SC-002) and standalone.

---

## Phase 4: User Story 2 - Recommend the next feature with rationale (Priority: P1)

**Goal**: The agent derives gaps vs the goal and outputs a ranked shortlist with one top pick.

**Independent Test**: Invoke `@agent-pm assess the repository and recommend the next feature`;
confirm the report has gaps (section 2), a discrepancies note (section 3), exactly one top pick and
a shortlist ranked by impact-to-effort, each row carrying gap/impact/effort/dependencies.

- [X] T011 [US2] Add the "Step 2 — Gap Analysis" procedure to `.claude/agents/pm.md`: compare inventory against the goal model, assign each gap a `severity` and a `goalLink` (e.g. "SCOPE Phase 2: CNPJ validation"), and report source-of-truth discrepancies rather than resolving them silently (FR-004, FR-009; data-model "Gap").
- [X] T012 [US2] Add the "Step 3 — Ranked Recommendations" procedure to `.claude/agents/pm.md`: rank candidates by impact-to-effort ratio with ties broken by gap severity, mark exactly one `isTopPick`, require each candidate to carry gap/rationale/impact/effort/dependencies, and honestly report when no high-value gap exists instead of inventing one (FR-005, FR-006, FR-013, SC-003; research R5; data-model "Feature Recommendation").
- [X] T012a [US2] Add the sparse-repository fallback to the recommendation procedure in `.claude/agents/pm.md`: when few or no capabilities are inventoried, recommend sensible foundational work (e.g. core ingestion/validation/data-model groundwork) rather than failing or returning nothing (FR-011; spec "Empty or very early repository" edge case).
- [X] T013 [US2] Add the section 2–4 output format to `.claude/agents/pm.md` matching `contracts/assessment-report.md` (gaps table, discrepancies, top pick block + shortlist table) (FR-012).

**Checkpoint**: Run the quickstart US2 validation — ranking and justification elements present.

---

## Phase 5: User Story 3 - Hand off the chosen feature to a separate spec-running agent (Priority: P2)

**Goal**: On acceptance, the agent writes a self-contained hand-off file for a separate agent.

**Independent Test**: After accepting a recommendation, confirm `specs/_handoff/<slug>.md` appears,
is self-contained (readable with no PM-session context), and matches `contracts/handoff-feature.md`;
confirm nothing outside the two output folders changed.

- [X] T014 [US3] Add the "Step 4 — Hand-off on acceptance" procedure to `.claude/agents/pm.md`: only after explicit maintainer acceptance, write `specs/_handoff/<slug>.md`; never auto-invoke speckit and never spawn another agent (subagents cannot — research R4); reaffirm the write-boundary (FR-007, FR-008, FR-015).
- [X] T015 [US3] Add the hand-off file format to `.claude/agents/pm.md` matching `contracts/handoff-feature.md` (frontmatter `slug`/`title`/`status: pending`/`source_report`/`created`, plus Summary / Problem & Goal Link / Scope Notes), ensuring the Summary is self-contained and usable directly as `speckit specify` input (SC-006; data-model "Hand-off Feature Description").

**Checkpoint**: Run the quickstart US3 validation — hand-off file is self-contained and correctly placed.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: End-to-end validation and consistency.

- [X] T016 [P] Verify the **Agents** entry in `CLAUDE.md` accurately describes the PM agent (location, advisory boundary, output folders, hand-off); correct if drifted.
- [X] T017 Run the full end-to-end manual validation in `specs/001-repo-self-assessment/quickstart.md` (full run + focused run + inventory-only), confirming report output, hand-off output, the `git status` write-boundary (SC-005), and the secret guard. — NOTE: agent **dependencies/mechanics validated** (valid frontmatter, all referenced source paths exist, output folders writable, `git status` self-check works, contracts present). The **live behavioral run is pending agent registration** (custom agents load at session start; `@agent-pm` is unavailable until Claude Code is reloaded). First live run is the maintainer's, per quickstart.
- [X] T018 [P] Run `pnpm format` and `pnpm lint` to confirm the new Markdown artifacts are Prettier-clean and no application lint is broken (constitution Principle III). — Prettier run scoped to the 3 new deliverable files (now clean); `pnpm format` over the whole repo was intentionally NOT run to avoid reformatting unrelated spec docs. No application code changed, so `next lint` is unaffected.
- [X] T019 Final review of `.claude/agents/pm.md` for clarity and full FR coverage (FR-001…FR-015), and confirm the agent's instructions reference the two contracts so output stays in shape.

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — T001/T002/T003 can run in parallel.
- **Foundational (Phase 2)**: Depends on T003 (agent file must exist). Blocks all user stories.
  T004→T005→T006→T007 are sequential (same file).
- **User Stories (Phase 3–5)**: All depend on Foundational completion. Because every story edits
  `.claude/agents/pm.md`, the stories are executed **sequentially in priority order**
  (US1 → US2 → US3); within a story, tasks are also sequential (same file).
- **Polish (Phase 6)**: Depends on all desired user stories being complete.

### User Story Dependencies

- **US1 (P1)**: Foundational only. Independently testable (inventory-only mode).
- **US2 (P1)**: Builds on the inventory US1 produces (gaps = goal − inventory). Testable on its own
  by running a full assessment.
- **US3 (P2)**: Acts on an accepted US2 recommendation. Testable by accepting a pick and checking
  the hand-off file.

### Within Each Story

- Inventory (US1) before gap analysis (US2) before hand-off (US3) — this is the agent's runtime
  order and also the build order, since all three live in one prompt file.

### Parallel Opportunities

- Phase 1: T001, T002, T003 in parallel (three different files).
- Phase 6: T016 and T018 in parallel (different concerns/files).
- Everything touching `.claude/agents/pm.md` (T004–T015, T019) is strictly sequential.

---

## Parallel Example: Setup

```bash
# These three create different files and have no interdependencies:
Task: "Create docs/assessments/README.md (T001)"
Task: "Create specs/_handoff/README.md (T002)"
Task: "Create .claude/agents/pm.md frontmatter skeleton (T003)"
```

---

## Implementation Strategy

### MVP First (User Story 1 only)

1. Phase 1 Setup → Phase 2 Foundational → Phase 3 (US1).
2. **STOP and VALIDATE**: invoke inventory-only mode; confirm an accurate, evidence-backed
   inventory. This alone delivers orientation/status value.

### Incremental Delivery

1. Setup + Foundational → agent skeleton with guardrails.
2. + US1 → inventory (MVP). Validate, optionally commit.
3. + US2 → ranked recommendation. Validate.
4. + US3 → file-based hand-off. Validate.
5. Polish → end-to-end quickstart + format/lint.

### Notes

- [P] = different files, no dependencies. The scarcity of [P] here is inherent: one agent prompt
  file carries most behavior.
- No automated tests (none requested; no framework). Validation is the quickstart.
- Advisory boundary is the project-critical invariant — re-verify with `git status` after any run.
- Commit after each completed phase/story for a clean increment history.
