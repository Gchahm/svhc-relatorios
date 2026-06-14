# Tasks: fix-document-findings agent (per-document autonomous false-positive correction)

**Feature**: `058-fix-document-findings-agent` | **Spec**: [spec.md](./spec.md) | **Plan**: [plan.md](./plan.md)

Tests ARE requested by the spec (Constitution III: spec explicitly requests unit + integration tests for
the new `reclassify` orchestration seam). The agent `.md` is reviewed against the CLI contracts, not
unit-tested (A6 / research Decision 6).

**Maximal reuse**: the resolver (`document-evidence`), the audited correction (`apply-correction` with
rollback + verify-after), and the propagation pipeline (`_propagate`) already ship. New code is one CLI
command (`reclassify`) and one agent prompt.

## Phase 1: Setup

- [x] T001 Confirm the dev environment can run the analysis CLI + tests: from repo root run `pnpm test:py` and (if Miniflare is up) `pnpm e2e:seed` so a synthetic period (`2099-01`) exists for manual verification. No code change.

## Phase 2: Foundational (blocking prerequisites)

- [x] T002 In `scripts/analysis/corrections.py`, add the public `reclassify(attachment_id, corrected_pages, *, target="local", cache_dir=DEFAULT_CACHE_DIR) -> dict` function: resolve `period` via `_attachment_context` (error if unknown); empty `corrected_pages` → `{"result": "no-op", ...}`; otherwise validate EACH page via `validate_page_fields` (raise `ValueError` on failure, before recording anything); record each page via `record_classification`; call the existing `_propagate(attachment_id, period, target, cache_dir)`; return `{"result": "reclassified", "attachment_id", "period", "pages": [...], "remote": target == "remote"}`. Reuses `_propagate`, `_attachment_context`, `validate_page_fields`, `record_classification` — no duplicated ordering (research Decision 1/2).

## Phase 3: User Story 4 — Composite reclassify CLI for safe ordering (Priority: P2, but foundational ergonomic primitive — built first)

**Goal**: a single `reclassify --attachment-id --pages` command that records corrected staging and
propagates in the pinned order, LOCAL by default.

**Independent test**: `python -m analysis reclassify --attachment-id <id> --pages '<json>'` against seeded
local D1 records staging, re-derives the analysis/documents/alerts, and leaves un-staged attachments
untouched.

- [x] T003 [US4] In `scripts/analysis/__main__.py`: add the `reclassify` subparser (`--attachment-id` required; `--pages`/`-`/stdin; `--cache-dir` default `CACHE_DIR`; `--remote`), import `reclassify` from `.corrections`, and add the handler mirroring `apply-correction`'s payload reading (string-or-stdin JSON, non-JSON/non-object → stderr error + exit 1; `ValueError` from validation → stderr `error: ...` + exit 1) and printing the result JSON to stdout. Update the module docstring's command list to mention `reclassify`.
- [x] T004 [P] [US4] Write `scripts/tests/test_reclassify.py` (stdlib `unittest`): pure-seam tests for `corrections.reclassify` — (a) empty pages → `no-op` (nothing recorded/propagated); (b) an invalid page payload raises `ValueError` and records NOTHING (validate-before-record; assert `record_classification` not called); (c) a valid payload records each page then calls `_propagate` exactly once with the resolved period (mock `record_classification`, `_propagate`, `_attachment_context`, `validate_page_fields`); (d) unknown attachment → error. Follow the existing `scripts/tests/_fixtures.py` + mock patterns (e.g. `test_corrections.py`).
- [x] T005 [P] [US4] Write `scripts/integration_tests/test_reclassify_d1.py` (real Miniflare D1, like `test_apply_staging_driven_d1.py`): seed the synthetic period, then assert `reclassify` of a synthetic attachment writes `page_classifications`, re-derives `attachment_analyses` (the corrected value lands), rebuilds `documents`, and refreshes `alerts`; assert a DIFFERENT un-staged attachment's analysis is unchanged (staging-driven safety). Scope all assertions to synthetic ids (memory `integration-tests-shared-d1-scope`). Idempotent restore between cases.

**Checkpoint**: `reclassify` works end-to-end and is the propagation primitive the design §4.5 specifies.

## Phase 4: User Story 1 — Autonomously correct a demonstrable misread (Priority: P1)

**Goal**: the agent corrects a false-positive misread autonomously, auditably, reversibly, via
`apply-correction`.

**Independent test**: given a seeded document whose recorded amount disagrees with a legible page, the
agent returns a `corrections` entry, `data_corrections` has an `applied` row, and the finding clears.

- [x] T006 [US1] Create `.claude/agents/fix-document-findings.md` per `contracts/fix-document-findings-agent.md`: YAML frontmatter (`name: fix-document-findings`, a precise `description` for delegation, `tools: Bash, Read, Glob`, `model: inherit`, a color), then the procedure — EVIDENCE (`document-evidence --id`), JUDGE (open `page_refs` images in own context), CORRECT only `false-misread` via `apply-correction --target-finding <mismatch_key> --pages <json-via-tempfile/stdin> --evidence <read_path>`, RESULT-MAP the `apply-correction` result codes to `corrections`/`left_as_finding`, and RETURN only the terse JSON. Include the §7 guardrails verbatim (evidence-bound, never touch true/page-error, preserve identity key on amount fixes, audited path only, escalate systematic faults, thread `--remote`, one doc per invocation, `.key`/`.dump` Bash-hook avoidance).

**Checkpoint**: the agent's happy-path correction is fully specified and exercised by its CLI primitives
(verified manually in T011).

## Phase 5: User Story 2 — Leave real findings and unreadable pages untouched (Priority: P1)

**Goal**: the agent never corrects `true` or `page-error` findings.

**Independent test**: a document whose page really disagrees → no `data_corrections` row, reported under
`left_as_finding` with reason `true`/`page-error`.

- [x] T007 [US2] In `.claude/agents/fix-document-findings.md`, ensure the JUDGE + RESULT-MAP sections explicitly route `true` → `left_as_finding (reason "true")` and `page-error` → `left_as_finding (reason "page-error")` with NO `apply-correction` call, and the evidence-bound rule ("when uncertain, LEAVE") is stated as the default. (Same file as T006 — fold in during T006; this task is the correctness-floor review of that file.)

## Phase 6: User Story 3 — Escalate systematic faults (Priority: P2)

**Goal**: the agent escalates systematic faults instead of mass-correcting.

**Independent test**: a finding attributed to a systematic root cause → no correction, reported under
`escalated` with `{area, hypothesis}`.

- [x] T008 [US3] In `.claude/agents/fix-document-findings.md`, ensure the JUDGE section names the `systematic-fault` bucket (roll-up precedence / grouping / reconciliation tolerance), routes it to `escalated` with `{area, hypothesis}` and NO data change, and references the §5 anti-pattern (don't hand-correct N docs for one code bug). (Same file as T006 — fold in during T006; this task is the escalation review of that file.)

## Phase 7: Polish & Cross-Cutting

- [x] T009 Update `CLAUDE.md`: add a bullet under "Important Patterns" / the triage-agent area documenting feature 058 — the `fix-document-findings` agent + the `reclassify` CLI, their relationship to `apply-correction` (audited) vs `reclassify` (un-gated §4.5), and that no schema/migration was added. Add an "Agents" entry for `fix-document-findings`.
- [x] T010 Run the quality gates: `pnpm lint`, `pnpm format` (prettier covers markdown incl. the agent `.md` + specs — memory `prettier-docs-ci-gate`), `pnpm test:py`, and `pnpm test:py:integration`. Fix any failures.
- [x] T011 Manual verification (non-UI): against seeded local D1, run `document-evidence` on a synthetic document, run `reclassify` on a synthetic attachment and confirm re-derivation + un-staged-untouched, and run an `apply-correction` round-trip + `list-corrections` to confirm the agent's audited path works end-to-end. Record results for the PR body.

## Dependencies

- T002 (the `reclassify` function) blocks T003/T004/T005.
- T006 (the agent file) subsumes T007/T008 (they are review passes over the same file written in T006).
- T009/T010/T011 are polish, after the code + agent land.
- US4 (CLI) is independent of US1/US2/US3 (agent) — they touch different files and can proceed in parallel
  after T002.

## Parallel execution examples

- After T002: `T004` and `T005` (the two test files) are `[P]` — different files, no interdependency.
- The agent file (T006) can be written in parallel with the CLI tests (T004/T005) — different files.

## Implementation strategy

MVP = US4 (the `reclassify` primitive, T002–T005) + US1/US2/US3 (the agent file, T006) — both are small and
ship together as one increment. The agent (US1/US2/US3) is the feature's headline; the CLI (US4) is the
ergonomic primitive design §4.5 calls for. Tests + the manual round-trip (T011) close the loop before the PR.
