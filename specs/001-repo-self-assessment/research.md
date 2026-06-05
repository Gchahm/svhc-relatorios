# Phase 0 Research: Repository Self-Assessment & Next-Feature Recommendation

All clarifications from the spec's Clarifications session are resolved here, plus the technical
unknowns surfaced while planning. Each item follows Decision / Rationale / Alternatives.

## R1. Delivery mechanism — how the assessment is realized

- **Decision**: A standalone Claude Code subagent defined at `.claude/agents/pm.md` (project
  scope, version-controlled). YAML frontmatter + Markdown system-prompt body.
- **Rationale**: The maintainer chose a "PM" agent running in its own separate context (spec
  Clarifications). Project-scoped agents are checked into the repo, discoverable by walking up
  from cwd, and invocable by name (`@agent-pm`) or via natural-language delegation through the
  `description` field. A separate context keeps the assessment reasoning isolated from
  implementation sessions.
- **Alternatives considered**:
  - *Speckit phase* (`speckit assess`): rejected — couples assessment to the speckit skill and
    its branch/spec lifecycle; the maintainer explicitly wanted a separate agent.
  - *Skill*: rejected — a skill runs inside the calling context rather than a separate one; the
    maintainer wanted separate-context isolation.
  - *Static checklist doc*: rejected — not repeatable or structured enough (FR-001).

## R2. Subagent definition format

- **Decision**: Frontmatter keys used: `name: pm`, `description:` (delegation trigger),
  `tools: Read, Grep, Glob, Bash, Write`, `model: inherit`, `color:` (cosmetic). Body holds the
  full operating instructions.
- **Rationale**: Only `name` + `description` are required; the rest are intentional. The agent
  needs read/search tools (`Read, Grep, Glob, Bash`) to inventory the repo and `Write` to emit
  the report and hand-off file. `Edit` is deliberately omitted to reduce the chance of mutating
  app code (the advisory constraint, FR-007, is still enforced primarily by instruction since
  `Write` could technically overwrite files). `model: inherit` follows the session model (the
  maintainer runs Opus 4.8), appropriate for a reasoning-heavy task.
- **Alternatives considered**:
  - Granting `Edit`/full tools: rejected — widens the blast radius against the advisory rule.
  - Pinning `model: opus`: acceptable, but `inherit` avoids drift if the default model changes.
  - Adding `Agent`/`Task` tool: rejected — subagents cannot spawn subagents (see R4), so it would
    be inert.

## R3. Output artifact & location (persistence)

- **Decision**: Each run writes a persisted, dated report to
  `docs/assessments/YYYY-MM-DD-assessment.md`. The folder is anchored with a committed
  `README.md`.
- **Rationale**: The maintainer chose a persisted dated report (spec Clarifications). `docs/`
  already holds project scope docs (`SCOPE-fraud-detection.md`), so assessments sit naturally
  beside them. Dated filenames give a diffable history and satisfy the "stale prior assessment"
  edge case (each run is a fresh file reflecting current state). If two runs occur on the same
  day, a `-2`/`-3` suffix is appended.
- **Alternatives considered**:
  - Ephemeral chat-only output: rejected by the maintainer's choice (no durable record).
  - Single overwritten `latest.md`: rejected — loses history and diff value.

## R4. Hand-off protocol to the spec-running agent

- **Decision**: On acceptance, the PM agent writes a self-contained feature description to
  `specs/_handoff/<slug>.md`. A *separate* agent that owns the speckit workflow later reads that
  file and runs `speckit specify` with its contents. Orchestration between the two agents happens
  at the main-session/human level, not by direct invocation.
- **Rationale**: **Claude Code subagents cannot spawn other subagents.** The documented pattern
  for nested delegation is to write state to disk for another agent (or chain from the main
  conversation). A file-based queue is exactly the maintainer's described design ("emit the
  feature into a folder … pass this task to another agent"). The `_handoff` prefix keeps the
  folder out of speckit's `^[0-9]{3}-` spec/branch glob so it never collides with real specs and
  the auto-numbering in `create-new-feature.sh` is unaffected.
- **Alternatives considered**:
  - PM agent directly invoking the speckit agent: impossible (subagent-spawn restriction).
  - PM agent running `speckit specify` itself: rejected — violates separation of concerns the
    maintainer asked for (PM recommends; a different agent specs/implements) and would mix
    contexts.
  - Hand-off via a top-level `pm-handoff/` dir: workable, but keeping it under `specs/` co-locates
    pending work with realized specs and is more discoverable for the spec-running agent.

## R5. Ranking method for candidate features

- **Decision**: Rank candidates by **impact-to-effort ratio** (best value-per-effort first), with
  ties broken by how critical the gap is to the fraud/forgery-detection goal. Impact and effort
  are each rated on a small ordinal scale (e.g. High/Medium/Low) with a one-line justification.
- **Rationale**: The maintainer chose impact-to-effort (spec Clarifications). An ordinal scale
  with explicit justification keeps rankings transparent and reproducible without false numeric
  precision, supporting SC-003 (every recommendation carries its justification elements).
- **Alternatives considered**:
  - Pure goal-impact ranking: rejected by choice (ignores effort/ROI).
  - Dependencies-first ordering: not the primary sort, but dependencies are still recorded per
    candidate (FR-006) and used as the practical sequencing note.

## R6. Goal reference & inventory sources

- **Decision**: The agent treats `docs/SCOPE-fraud-detection.md` as the canonical statement of the
  project's end goal (with the spec's north-star summary as backup). For the inventory, it reads
  across: `src/app/api/*` and `src/app/dashboard/*` (feature surface), `src/db/fiscal.schema.ts`
  (+ `schema.ts`, `auth.schema.ts`) (data model), `scripts/scraper/` (ingestion), `data/scrape/`
  (available inputs), `docs/` (scope & migration notes), `README.md`, `CLAUDE.md`, the
  constitution, prior `specs/` and `docs/assessments/`, and recent git history.
- **Rationale**: Grounding recommendations in the documented fraud-detection roadmap keeps them
  goal-aligned (FR-004). Reading code + docs + git lets the agent flag source-of-truth
  discrepancies (FR-009) and avoid recommending what already exists (SC-002).
- **Alternatives considered**:
  - Code-only inventory: rejected — would miss the documented roadmap and produce off-goal picks.
  - Hardcoding a capability list in the agent prompt: rejected — would go stale; the agent must
    re-derive state each run (FR-001, stale-assessment edge case).

## R7. Advisory write-boundary enforcement

- **Decision**: Enforce the no-app-mutation rule by (a) instruction — the agent's only permitted
  writes are `docs/assessments/**` and `specs/_handoff/**`; and (b) a self-check — before
  finishing, the agent runs `git status --porcelain` and confirms no files outside those two
  paths changed, reporting the result.
- **Rationale**: `Write` is required for outputs, so a hard tool block isn't possible; an explicit
  rule plus a verifiable `git status` self-check makes SC-005 checkable and surfaces accidental
  edits immediately.
- **Alternatives considered**:
  - Relying on tool restriction alone: insufficient, since `Write` is needed and is unrestricted
    by path.
  - A git pre-commit hook: out of scope for this feature; the self-check is lighter and lives with
    the agent.

## R8. Secret-handling guard

- **Decision**: The agent must never read for the purpose of surfacing, nor echo, secret values
  (e.g. contents of `scripts/.env`, tokens, keys). It may note that a secret/config file exists
  without reproducing its values.
- **Rationale**: Constitution Principle IV (Security & Auth by Default); the agent traverses the
  whole repo, so an explicit guard prevents leaking credentials into a committed report.
- **Alternatives considered**: Blanket-excluding `.env` from reads — partially effective but
  brittle; an explicit "never reproduce secret values" instruction generalizes better.
