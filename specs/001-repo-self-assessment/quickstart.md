# Quickstart: PM Agent — Repository Self-Assessment

How to invoke the PM agent and validate it behaves per the spec. No automated tests exist
(constitution Principle III); validation is manual against the acceptance scenarios.

## Prerequisites

- The agent file exists at `.claude/agents/pm.md`.
- Output folders are anchored: `docs/assessments/README.md` and `specs/_handoff/README.md`.
- Working tree is clean before you start (so the write-boundary check is meaningful).

## Invoke

Full assessment:

```text
@agent-pm assess the repository and recommend the next feature to build
```

Focused run (optional per-run focus, FR-010):

```text
@agent-pm assess the repo with a focus on document forgery detection
```

Inventory only (US1 standalone):

```text
@agent-pm produce a current-state capability inventory only — no recommendations
```

## Validate (maps to acceptance scenarios)

1. **US1 — Inventory** (FR-002, FR-003, SC-002): The report's section 1 lists capabilities across
   categories, each with a real path in `Evidence`, and marks maturity. Spot-check that known
   capabilities (e.g. `alerts` API at `src/app/api/alerts/`, fiscal schema at
   `src/db/fiscal.schema.ts`, scraper at `scripts/scraper/`) appear.
2. **US2 — Recommendation** (FR-004, FR-005, FR-006, SC-003): Section 4 has exactly one top pick
   and a ranked shortlist; every row has Impact, Effort, Gap, Dependencies. Ranking follows
   impact-to-effort order.
3. **US3 — Hand-off** (FR-008, SC-006): After you accept a pick, a `specs/_handoff/<slug>.md` file
   appears matching `contracts/handoff-feature.md`, and it reads as self-contained.
4. **Advisory boundary** (FR-007, SC-005): Run `git status --porcelain`. The ONLY changes are
   under `docs/assessments/` and (if you accepted) `specs/_handoff/`. The report's section 5
   states this result.
5. **No-gap honesty** (FR-013): On a hypothetical fully-covered state, confirm the agent says so
   rather than inventing a low-value pick.
6. **Secret guard** (R8): Confirm the report does not reproduce any secret values (e.g. from
   `scripts/.env`).

## Expected outputs

- `docs/assessments/<YYYY-MM-DD>-assessment.md` — always.
- `specs/_handoff/<slug>.md` — only when a recommendation is accepted.

## Hand-off to the spec workflow (separate agent)

In a separate session/agent that owns speckit:

```text
Read specs/_handoff/<slug>.md and run /speckit specify using its Summary as the feature description.
```

This downstream step is outside this feature's scope; it's listed so the end-to-end loop is clear.
