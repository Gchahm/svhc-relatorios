# Contract: `/improve-classification` orchestrator skill (US3)

The thin loop. A **non-forked skill** (`.claude/skills/improve-classification/SKILL.md`) that runs in
the **main** conversation so it can spawn the isolated workers (a subagent cannot). It coordinates and
tracks **no** state of its own beyond what the Python CLI returns — it never reads page images, full
artifacts, or diffs (FR-005/FR-011/SC-002).

## Invocation

```
/improve-classification <period> [--document-id <ids…>] [--entry-id <ids…>] [--max-iterations 3]
```

Initial scope = the period, or the passed subset. `--max-iterations` / `--no-progress-window` forward
to `loop-state`.

## Loop algorithm

```
iteration ← 1
scope     ← initial scope (period or subset)
repeat:
  1. ANALYZE  — delegate to the `analyze-docs` agent (Agent tool) for `scope`.
                Receive ONLY its terse mismatch summary.
  2. STATE    — `python -m analysis loop-state --periodo <p> --iteration <iteration> [scope flags]`.
                If `terminate` is set → go to REPORT.
  3. REVIEW   — for each OPEN mismatch with no current-iteration verdict, delegate the
                `review-mismatch` agent (Agent tool), one mismatch per call, in parallel.
                For each returned verdict: `record-verdict --periodo <p> --iteration <iteration> --json …`.
  4. ACT on verdicts:
       • true       → leave as a finding (never fix).
       • page-error → leave as data-quality (never fix).
       • transient  → if not already re-tried this loop, add its document to `scope` for the next
                      iteration (one re-classification attempt); do NOT delegate a fix.
       • false      → delegate the `fix-mismatch` worker (Agent tool) with the mismatch + root_cause.
                      Record the returned PR ref via `record-verdict --fix-*`.
  5. RESCOPE  — `python -m analysis loop-state --periodo <p>` → `affected_document_ids`.
                `scope ← --document-id affected_document_ids` (Decision 8 / SC-006).
                If `terminate` is set → REPORT. Else `iteration ← iteration + 1`; repeat.

REPORT: print findings (all `true`), data-quality (`page-error`), open false mismatches with their
        fix PRs, the termination reason, and the iteration count. Never merge anything.
```

## Guarantees the skill MUST uphold

- **Delegation only** (FR-005): every vision/judgment/codegen step is a separate Agent call; the
  orchestrator handles only ids + terse JSON. It MUST NOT open page images or run `classify-*`/
  `apply-extractions` itself (that is inside `analyze-docs`).
- **Scoped re-runs** (FR-009/SC-006): iterations after the first pass `--document-id` from
  `affected_document_ids`, never the whole period.
- **Findings preserved** (FR-010/SC-004): `true` mismatches are reported every iteration and never
  fixed or suppressed.
- **Human-gated** (FR-008/SC-005): fixes may open PRs; the loop NEVER merges or pushes to `main`.
- **Always terminates** (FR-009/SC-005): the loop stops the instant `loop-state` reports `terminate`
  (`converged` / `max-iterations` / `no-progress`). The orchestrator does not invent its own stop
  logic — it obeys the deterministic signal.
- **Minimal state** (FR-011): no verdict/iteration state is kept in the orchestrator's prose; it is
  read back from `loop-state` each turn.

## Edge cases (mapped to spec)

- Nothing to analyze → `analyze-docs` reports "nothing to do"; `loop-state` → `converged`; report and
  stop.
- Subset doc with no images → skipped with a recorded reason (handled in `docs-plan`/review evidence
  step); surfaces as `page-error` if it reaches review.
- Verdict flips across iterations / fix causes a regression → `loop-state` raises `no-progress`;
  loop halts instead of re-fixing forever.
