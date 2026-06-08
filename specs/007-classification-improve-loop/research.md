# Phase 0 Research: Self-Improving Document-Classification Loop

All open spec questions were resolved in the Clarifications session (2026-06-08); this file records
the resulting design decisions, their rationale, and the alternatives rejected. There are no
remaining `NEEDS CLARIFICATION` items.

## Decision 1 — US1 is reused as-is; this branch builds US2 + US3

- **Decision**: Treat the `analyze-docs` agent (+ `classify-period`/`classify-doc-page` skills + the
  `python -m analysis` chain) as the finished, frozen **step 1**. Build only the **review** (US2) and
  the **orchestrator loop** (US3) here.
- **Rationale**: Validation during clarify confirmed `analyze-docs` already satisfies FR-001–FR-005
  (subset targeting via `--document-id`/`--entry-id`, deterministic merge+checks, terse `mismatches`
  hand-back). FR-001 forbids a parallel vision implementation, so the loop must consume the existing
  summary verbatim.
- **Alternatives considered**: Re-implementing a richer vision step that also emits page refs in the
  mismatch summary — rejected: it duplicates the skill, violates FR-001, and the review worker can
  resolve page images itself from the manifest (Decision 5).

## Decision 2 — The reviewer is an automated, context-isolated Claude-vision agent

- **Decision**: A new `review-mismatch` agent (Markdown subagent, `tools: Read, Glob, Bash`,
  `model: inherit`) judges one mismatch at a time from the page image(s) + ledger entry and returns a
  terse verdict. No human-in-UI review step; no dashboard work.
- **Rationale**: The loop must run many iterations unattended (clarify Q1). An isolated subagent that
  reads images and returns only a small verdict keeps the orchestrator's context clean (FR-005,
  SC-002), mirroring how `analyze-docs` is structured. The Read tool can view page images here
  (the retired mlx_vlm constraint does not apply — see project memory).
- **Alternatives considered**: (a) Human-in-UI review — rejected: breaks the autonomous loop, needs
  Next.js/D1 work the spec scopes out. (b) Folding review into `analyze-docs` — rejected: mixes the
  "what disagrees" (deterministic) with the "is it our fault" (judgment) concerns and would re-read
  every page each loop; keeping them separate lets review run per-mismatch and in parallel.

## Decision 3 — Verdicts + loop state persist as one per-period JSON working file

- **Decision**: Persist to `data/scrape/<period>.verdicts.json`: a list of verdict records (keyed by
  a stable **mismatch identity**) plus a small loop-state block (iteration history). No D1 table.
- **Rationale**: Clarify Q2 chose JSON working files; matches the spec assumption and the existing
  pattern of sibling artifacts under `data/scrape/` (`<period>.extract-todo.json`,
  `<image>.classify.json`). Keeping it as a file makes runs resumable and auditable without a
  migration, and lets the deterministic CLI own all reads/writes (SC-003).
- **Alternatives considered**: (a) New D1 table(s) — rejected by clarify (contradicts the assumption,
  adds schema/migration, Constitution I). (b) In-memory only — rejected: no audit trail, no resume,
  and would force the orchestrator to hold verdict state (violates the "thin orchestrator", FR-011).

## Decision 4 — Mismatch identity = a deterministic key over the mismatch's stable fields

- **Decision**: Identify a mismatch by `period` + `kind` + (`document_id`/`entry_id`, or for
  `duplicate_billing` the sorted `document_ids`). This key is the join between a `mismatches` row, its
  stored verdict, and the loop's open/closed accounting.
- **Rationale**: The `mismatches` command emits no stable id of its own; the loop needs to recognise
  "the same mismatch" across iterations to detect convergence and no-progress (FR-009). The chosen
  fields are exactly the stable identity columns already present in the summary
  (`summarize_mismatches`).
- **Alternatives considered**: Hashing the full mismatch row (including extracted values) — rejected:
  a re-read that changes the extracted amount would look like a *new* mismatch every iteration and the
  loop would never converge; identity must exclude the volatile extracted value.

## Decision 5 — `page_refs` are added to the mismatch summary; the review worker consumes them directly

- **Decision**: Extend `summarize_mismatches` so each mismatch carries `page_refs` —
  `[{document_id, page_label, read_path}]` (absolute `read_path`s) for the document(s) behind the
  mismatch (per-document kinds: the one document; `duplicate_billing`: one group per
  `document_ids[]`). The review worker opens those `read_path`s with the Read tool and reads the
  ledger entry from `data/scrape/<period>.json`. This **closes FR-004**, which explicitly requires
  page reference(s) in the summary (analyze finding C1).
- **Rationale**: FR-004 names "page reference(s)" as a required field of the summary, so the summary —
  not a side artifact — should carry them; this makes the requirement literally true and decouples the
  review worker from the `<period>.extract-todo.json` manifest (which only lists representative pages
  and may be re-scoped between steps). The read_paths derive from the document's existing `file_path`
  tokens (the same source `docs-plan` uses), so it is a thin, deterministic addition — not a parallel
  extractor, so FR-001/Decision 1 still hold.
- **Alternatives considered**: (a) Reading page paths from the `<period>.extract-todo.json` manifest —
  rejected (analyze C1): leaves FR-004's text unsatisfied and couples review to a manifest that
  carries only representatives and is rewritten per scope. (b) Leaving the gap documented but unfixed —
  rejected by the maintainer; FR-004 should hold literally.

## Decision 6 — The orchestrator is a skill that runs in the MAIN context

- **Decision**: Implement US3 as `/improve-classification` — a **non-forked skill** invoked in the
  main conversation. Its instructions drive the loop by delegating each heavy step to a subagent via
  the Agent tool (`analyze-docs`, `review-mismatch`, `fix-mismatch`) and calling the Python
  `loop-state`/`record-verdict` commands for bookkeeping.
- **Rationale**: A subagent cannot spawn subagents (confirmed by the `pm` agent's own note). The
  orchestrator's whole job is to spawn isolated workers, so it must live where it can — the main
  context. "Thin" is enforced by instruction: it never reads page images or diffs itself; it only
  passes ids around and reads terse JSON. This keeps its context flat (SC-002) even though it is the
  top-level loop.
- **Alternatives considered**: (a) Orchestrator as a subagent — rejected: it could not spawn the
  workers. (b) A standalone Python driver that shells out to Claude — rejected: it cannot drive the
  vision/judgment agents, which are Claude-Code-native, and adds a parallel control plane.

## Decision 7 — Deterministic stop conditions live in Python, not in the model

- **Decision**: `python -m analysis loop-state --periodo P` computes, from `verdicts.json` +
  current `mismatches`: the open mismatch set, the per-iteration history, the set of documents to
  re-scope next iteration, and a **terminate** signal with a reason — `converged` (no `false`/unresolved
  mismatches), `max-iterations` (default cap **3**), or `no-progress` (the open-mismatch set did not
  shrink, or the same mismatch id flipped verdict / recurred, across **2** consecutive iterations).
- **Rationale**: FR-009/SC-005 require guaranteed termination and SC-003 requires reproducibility.
  Putting the arithmetic in deterministic Python (not in the orchestrator's prose) makes termination
  provable and the working set reproducible regardless of model variation. Thresholds are constants
  with CLI overrides (`--max-iterations`, `--no-progress-window`) so they are tunable without code
  changes to the agents.
- **Alternatives considered**: Letting the orchestrator "decide when to stop" from context —
  rejected: non-deterministic, unauditable, and risks infinite loops (the exact failure SC-005
  guards against).

## Decision 8 — Re-runs after iteration 1 are scoped to affected documents

- **Decision**: Iteration 1 analyzes the requested scope (period or initial subset). Every later
  iteration re-runs `analyze-docs` with `--document-id` limited to the documents implicated in the
  still-open mismatches (and those just touched by a fix), as reported by `loop-state`.
- **Rationale**: SC-006/FR-009 require scoped re-runs so each iteration is cheap (SC-001); the
  affected-doc set is derivable deterministically from the open mismatches.
- **Alternatives considered**: Re-running the whole period each iteration — rejected: violates
  SC-001/SC-006 and defeats the point of subset targeting built in US1.

## Decision 9 — The fix worker runs the speckit pipeline on a branch and opens a PR; never merges

- **Decision**: A new `fix-mismatch` agent receives one `false` mismatch + its root-cause hypothesis,
  runs the spec-driven workflow (via the `speckit` skill) on a dedicated branch to implement the fix,
  and **opens a PR with `gh`**. It never merges and never pushes to `main`. It returns only a terse
  result (PR url/branch + one-line summary).
- **Rationale**: Clarify Q3 chose "open a PR, never merge"; FR-008/SC-005 require human-gated fixes.
  Reusing speckit keeps fixes spec-driven and reviewable. Running in an isolated subagent (optionally
  a git worktree) keeps the heavy codegen out of the orchestrator's context (FR-005).
- **Alternatives considered**: (a) Prepare a spec/branch only, no PR — rejected by clarify (less
  autonomous than chosen). (b) Auto-apply/merge — rejected: violates the human gate
  (FR-008/SC-005). (c) Record a proposal only — rejected by clarify.

## Decision 10 — True / transient / page-error are surfaced, never "fixed"

- **Decision**: `true` mismatches are preserved and reported as findings every iteration and are
  never queued for a fix (FR-010/SC-004). `transient` triggers at most one re-classification of that
  document (not a code fix); if the same value recurs it becomes a no-progress signal (FR-007, US2
  scenario 3). `page-error` (missing/illegible image) is recorded as a data-quality item, not a
  finding and not a code-fix candidate (edge cases).
- **Rationale**: Directly encodes FR-007, FR-010, and the spec's edge cases; prevents the loop from
  trying to "fix" genuine findings or chasing non-deterministic re-reads forever.
- **Alternatives considered**: Treating `transient` like `false` (queue a fix) — rejected: wastes fix
  cycles on noise and risks regressions; treating `page-error` as `true` — rejected: it is not a
  document-vs-ledger disagreement.
