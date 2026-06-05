# Feature Specification: Repository Self-Assessment & Next-Feature Recommendation

**Feature Branch**: `001-repo-self-assessment`
**Created**: 2026-06-05
**Status**: Draft
**Input**: User description: "Create a skill/mechanism enabling the agent to reassess the current state of the repository (inventory features and capabilities) and recommend the next feature to implement, in service of the project goal: verifying scraped fiscal data/docs for correctness and detecting forgery/corruption."

## Overview

This feature delivers a **repeatable assessment mechanism** that the maintainer can invoke at
any time to get an honest, evidence-based picture of what the project can do today and a
prioritized recommendation for what to build next. Unlike a normal product feature, its "users"
are the people steering the project's direction, and its output is decision support — not a
change to the deployed fiscal-auditing application itself.

The recommendation is always anchored to the project's north star: ensuring scraped fiscal
data and documents are correct, and surfacing signs of forgery or corruption.

## Clarifications

### Session 2026-06-05

- Q: How should the assessment mechanism be realized in the repo? → A: A standalone "PM" agent
  at `.claude/agents/pm` running in its own separate context (not a skill or a speckit phase).
- Q: Where should each assessment's output be stored? → A: A persisted, dated report file
  committed into the repository.
- Q: How should candidate next-features be ranked? → A: By impact-to-effort ratio (best
  value-per-effort first), tie-broken by how critical the gap is to the project goal.
- Q: On accepting a recommendation, how should hand-off to the spec workflow happen? → A: The PM
  agent writes the chosen feature into a hand-off folder; a separate agent (which runs the
  speckit workflow) picks it up from there. The two agents have separate contexts.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Inventory current capabilities (Priority: P1)

As the project maintainer, I want to ask the agent to produce a current-state inventory of the
repository — what features and capabilities exist today — so that I have a trustworthy baseline
of what the project actually does without manually re-reading the whole codebase.

**Why this priority**: Every recommendation depends on an accurate picture of the present. An
inventory is independently valuable on its own (orientation, onboarding, status reporting) and
is the foundation the rest of the feature builds on.

**Independent Test**: Invoke the mechanism in "inventory only" mode and confirm it returns a
structured list of the project's existing capabilities (e.g. data domains managed, auditing
checks present, ingestion/scrape handling, reporting) that matches what a manual review of the
repository would find, with no recommendations attached.

**Acceptance Scenarios**:

1. **Given** the repository in its current state, **When** the maintainer requests an
   assessment, **Then** the agent produces a categorized inventory of existing features and
   capabilities, each backed by a concrete reference to where it lives in the project.
2. **Given** a capability that exists in the code, **When** the inventory is produced, **Then**
   that capability appears in the inventory (no major existing capability is silently omitted).
3. **Given** the inventory is produced, **When** the maintainer reviews it, **Then** it
   distinguishes capabilities that are complete from those that are partial or stubbed.

---

### User Story 2 - Recommend the next feature with rationale (Priority: P1)

As the project maintainer, I want the agent to compare the current capabilities against the
project's end goal (correctness verification and forgery/corruption detection) and recommend the
single most valuable next feature, with a clear rationale, so that I can decide what to build
next with confidence.

**Why this priority**: This is the core purpose of the request. Without a reasoned
recommendation tied to the project goal, the inventory is just description, not direction.

**Independent Test**: Invoke the mechanism and confirm it outputs one clearly-identified
recommended next feature plus the reasoning that connects it to the project goal and to a gap
found in the inventory. The recommendation can be evaluated for soundness without writing any
code.

**Acceptance Scenarios**:

1. **Given** a completed capability inventory, **When** the agent evaluates gaps against the
   project goal, **Then** it produces a prioritized shortlist of candidate next features and
   designates one top recommendation.
2. **Given** a recommended next feature, **When** the maintainer reads it, **Then** the
   recommendation states the gap it closes, why it advances correctness/forgery-detection, its
   rough effort/impact, and its dependencies on existing capabilities.
3. **Given** the maintainer disagrees with the top pick, **When** they review the shortlist,
   **Then** the alternatives and the reasoning are visible so they can choose a different one.

---

### User Story 3 - Hand off the chosen feature to a separate spec-running agent (Priority: P2)

As the project maintainer, once I accept a recommendation, I want the PM agent to drop the chosen
feature into a hand-off folder so that a separate agent — running in its own context and owning
the spec-driven workflow — can pick it up and begin specifying it without me re-explaining it.

**Why this priority**: It closes the loop from "what next" to "let's build it," but the feature
still delivers full value (a defensible recommendation) without the automated hand-off, so it is
secondary to P1.

**Independent Test**: After a recommendation is accepted, confirm a ready-to-use feature
description for the chosen item appears in the hand-off folder in a form a separate spec-running
agent can consume directly, and that nothing is implemented automatically without the
maintainer's approval.

**Acceptance Scenarios**:

1. **Given** an accepted recommendation, **When** the maintainer asks to proceed, **Then** the
   PM agent writes a concise, self-contained feature description into the hand-off folder,
   suitable as the starting input for a new spec by a separate agent.
2. **Given** a feature description placed in the hand-off folder, **When** the separate
   spec-running agent reads it, **Then** it has enough context to begin the spec workflow without
   consulting the PM agent's session.
3. **Given** any recommendation, **When** it is produced, **Then** no application code or schema
   is changed as a side effect of running the assessment (the only repository writes are the
   assessment report and the hand-off feature description).

---

### Edge Cases

- **Empty or very early repository**: When few capabilities exist, the assessment must still
  produce a sensible recommendation (e.g. foundational capabilities) rather than failing or
  returning nothing.
- **Conflicting evidence**: When the code and the documentation disagree about whether a
  capability exists, the assessment must report the discrepancy rather than silently trusting
  one source.
- **Goal drift**: When the maintainer states a different priority for this run (e.g. "focus on
  reporting" instead of detection), the recommendation must respect the stated focus while still
  noting how it relates to the overall goal.
- **Stale prior assessment**: When the repository has changed since the last assessment, a new
  run must reflect the current state, not a cached prior conclusion.
- **No meaningful gap**: When the agent cannot find a high-value gap, it must say so honestly
  rather than inventing a low-value recommendation.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The mechanism MUST be invocable on demand by the maintainer as a repeatable
  action, producing a fresh assessment each time it is run.
- **FR-002**: The mechanism MUST produce a categorized inventory of the repository's existing
  features and capabilities, each item supported by a concrete reference to its location in the
  project.
- **FR-003**: The inventory MUST distinguish complete capabilities from partial, stubbed, or
  planned ones.
- **FR-004**: The mechanism MUST evaluate the inventory against the stated project goal
  (verifying correctness of scraped fiscal data/documents and detecting forgery/corruption) and
  identify gaps relative to that goal.
- **FR-005**: The mechanism MUST output a prioritized shortlist of candidate next features and
  designate exactly one top recommendation. Candidates MUST be ranked by impact-to-effort ratio
  (best value-per-effort first), with ties broken by how critical the gap is to the project goal.
- **FR-006**: Each candidate MUST include: the gap it addresses, its rationale tied to the
  project goal, a rough impact and effort estimate (the basis of its ranking), and its
  dependencies on existing capabilities.
- **FR-007**: The mechanism MUST be advisory with respect to the application — running an
  assessment MUST NOT modify application code, schema, or data. The only repository writes it may
  make are (a) its own assessment report and (b) the hand-off feature description (FR-008, FR-014).
- **FR-008**: Upon the maintainer accepting a recommendation, the PM agent MUST write a concise,
  self-contained feature description into a designated hand-off folder, in a form a separate
  agent (which runs the spec-driven workflow in its own context) can consume directly without
  access to the PM agent's session.
- **FR-014**: Each assessment run MUST produce a persisted, dated report file committed within
  the repository, capturing the capability inventory, identified gaps, and the ranked
  recommendations for that run.
- **FR-015**: The PM agent MUST run in its own separate context, distinct from the agent that
  performs the spec-driven workflow; hand-off between them occurs only via the hand-off folder.
- **FR-009**: The mechanism MUST report discrepancies between sources of truth (e.g. code vs
  documentation) rather than silently resolving them.
- **FR-010**: The mechanism MUST accept an optional maintainer-supplied focus for a given run and
  honor it while relating it back to the overall goal.
- **FR-011**: The mechanism MUST behave sensibly on a sparse repository, recommending
  foundational work instead of failing.
- **FR-012**: The assessment output MUST be expressed in plain, decision-ready language that the
  maintainer can evaluate without reading the codebase.
- **FR-013**: The mechanism MUST honestly report when no high-value next feature can be
  identified, rather than fabricating one.

### Key Entities *(include if feature involves data)*

- **Capability Inventory**: The structured snapshot of what the project does today. Attributes:
  category, capability name, maturity (complete/partial/stub/planned), evidence/location.
- **Project Goal Model**: The reference standard the inventory is measured against — correctness
  verification of scraped fiscal data/documents and detection of forgery/corruption — optionally
  narrowed by a per-run focus.
- **Gap**: A discrepancy between current capabilities and the project goal. Attributes:
  description, severity relative to goal, affected capability area.
- **Feature Recommendation**: A proposed next feature. Attributes: title, the gap it closes,
  rationale, impact estimate, effort estimate, impact-to-effort rank within the shortlist, and a
  flag indicating whether it is the top pick.
- **Assessment Report**: The persisted, dated artifact for a single run. Attributes: run date,
  the capability inventory, the gaps, and the ranked recommendations.
- **Hand-off Feature Description**: The self-contained description of an accepted recommendation,
  written into the hand-off folder for a separate spec-running agent to consume.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A maintainer can obtain a complete current-state assessment in a single invocation,
  without manually pointing the agent at specific files.
- **SC-002**: The capability inventory captures at least 90% of the project's significant
  existing capabilities when spot-checked against a manual review.
- **SC-003**: Every recommendation produced includes all required justification elements (gap,
  goal-tied rationale, impact, effort, dependencies) — 100% of the time.
- **SC-004**: In at least 80% of assessment runs on a non-trivial repository state, the
  maintainer judges the top recommendation to be a reasonable and relevant next step.
- **SC-005**: Running an assessment never changes application code, schema, or data — verifiable
  by a working tree whose only changes are the assessment report and (on acceptance) the hand-off
  feature description.
- **SC-006**: A separate spec-running agent can begin the spec workflow from the hand-off feature
  description alone, with no re-explanation and no access to the PM agent's session.

## Assumptions

- The mechanism is **advisory and human-in-the-loop**: it recommends and, on approval, hands off
  the chosen feature, but it does not autonomously implement features or run the spec workflow
  itself.
- The deliverable is realized as a standalone "PM" agent at `.claude/agents/pm`, running in its
  own separate context — not as a skill, a speckit phase, or a runtime feature of the deployed
  fiscal application. It changes how the project is steered, not what the app does at runtime.
- Hand-off is agent-to-agent via a designated folder: the PM agent writes the accepted feature
  description there, and a separate agent that owns the spec-driven (speckit) workflow consumes
  it. The exact folder location is a planning-phase decision.
- The project's end goal is treated as the fixed evaluation standard unless the maintainer
  supplies a per-run focus.
- Output is consumed primarily by the maintainer (and the agent during hand-off), not by
  external end users.
- The assessment reflects the repository state at the moment of invocation; it is regenerated
  each run rather than relying on a persisted prior result.
