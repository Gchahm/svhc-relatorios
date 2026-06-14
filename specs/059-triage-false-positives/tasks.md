# Tasks: triage-false-positives skill (batch orchestrator over open findings)

**Feature**: `059-triage-false-positives` | **Spec**: [spec.md](./spec.md) | **Plan**: [plan.md](./plan.md)

The deliverable is a single orchestrator prompt file, `.claude/skills/triage-false-positives/SKILL.md`
(mirrors `improve-classification/SKILL.md`). All tasks edit that one file (so they are sequential, not
`[P]`) except the verification tasks. No application code, no CLI, no schema.

## Phase 1: Setup

- [x] T001 Create the skill directory `.claude/skills/triage-false-positives/` and an empty
  `SKILL.md` with valid frontmatter (`description`, `argument-hint: "[period] [--kind k…] [--entry-id
  id…] [--remote]"`, `allowed-tools: Task, Bash`).

## Phase 2: Foundational

- [x] T002 In `.claude/skills/triage-false-positives/SKILL.md`, write the **Purpose** + **Input** +
  **Boundaries** sections: delegation-only, holds no page images, runs no corrections/classification
  itself, never merges/pushes, threads `--remote` explicitly (FR-006, FR-010, FR-011, SC-002).

## Phase 3: User Story 1 — Scrub a whole period (Priority: P1) 🎯 MVP

**Goal**: list candidates read-only, fan out one agent per candidate in parallel, aggregate, report.

**Independent test**: run `triage-false-positives 2099-01`; the amount finding folds into the document
candidate → expect 1 agent dispatched (document `37f12d05…`, covering both findings), a summary
aggregating its result, zero orchestrator image reads.

- [x] T003 [US1] In `SKILL.md`, write the **List candidates** step: run `cd scripts && uv run python
  -m analysis mismatches --periodo <p> [--remote]` (read-only), parse JSON, derive `candidate_id =
  document_id ?? attachment_id`, fold a per-attachment finding into a covering document candidate, and
  de-duplicate by candidate id (FR-002, FR-004).
- [x] T004 [US1] In `SKILL.md`, write the **Fan-out** step: dispatch one `fix-document-findings`
  agent per distinct candidate via the Task tool, all in ONE message (parallel), prompt = candidate
  id + target flag; never open `page_refs` (FR-003, SC-003, SC-002).
- [x] T005 [US1] In `SKILL.md`, write the **Aggregate + Report** step: collect each agent's terse
  JSON, sum into `{candidates, corrected, left-by-reason, escalated[]}`, print one concise summary
  (FR-007, SC-004); per the data-model summary shape.

## Phase 4: User Story 2 — Filter a slice (Priority: P2)

**Goal**: triage only findings matching `--kind` and/or `--entry-id`.

**Independent test**: `triage-false-positives 2099-01 --kind amount` → the overpayment row is filtered
out, so the amount finding has no covering surviving document candidate and is dispatched as an
`attachment` candidate (`296993de…`) → 1 agent.

- [x] T006 [US2] In `SKILL.md`, extend the **List candidates** step to forward `--entry-id <id…>` to
  the `mismatches` CLI and apply a client-side `--kind <kind…>` filter over its JSON output before
  deriving candidates (FR-001, FR-005).

## Phase 5: User Story 3 — Nothing to triage / error isolation (Priority: P3)

**Goal**: zero candidates ⇒ no dispatch; one bad agent ⇒ `agent-error`, batch continues.

**Independent test**: `triage-false-positives <empty-period>` → 0 agents, "nothing to triage". A
failing agent is counted `agent-error` and the rest still run.

- [x] T007 [US3] In `SKILL.md`, write the **empty-set guard** (zero candidates ⇒ dispatch nothing,
  report a zero-candidate summary, no error — FR-009) and the **error-isolation** rule (an
  errored/un-parseable agent ⇒ count its candidate `agent-error` under `left`, continue — FR-008,
  SC-005).

## Phase 6: Polish & Verification

- [x] T008 Run `node_modules/.bin/prettier --write` on the new `SKILL.md` and the `specs/059-*`
  markdown; confirm `node_modules/.bin/prettier --check` passes (constitution III / CI gate).
- [x] T009 Verify against local seed: confirm `mismatches --periodo 2099-01` lists 2 rows that fold to
  1 document candidate, that `document-evidence --id <doc>` resolves it (covering both findings), and
  that `mismatches --attachment-id <id>` works as the attachment-candidate evidence fallback; confirm
  the orchestrator opened no page image while deriving candidates (SC-001..SC-005, quickstart). (The
  live agent fan-out runs in a fresh session, where the merged `fix-document-findings` agent loads.)

## Dependencies

- T001 → T002 → (T003 → T004 → T005) → T006 → T007 → T008 → T009. All edit the same file, so
  sequential. US1 (T003–T005) is the MVP and is independently testable once done.

## Implementation strategy

MVP = Phases 1–3 (US1): a working period-wide triage. US2 (filter) and US3 (guards) are additive
refinements to the same single file. Verification (T009) is a live run, since skills have no unit-test
harness in this repo.
