# Contract: `fix-mismatch` worker agent (US3)

The context-isolated **fix worker**. Given one `false` mismatch + its root-cause hypothesis, it
improves the system via the spec-driven workflow and **opens a PR** — it never merges. Heavy codegen
stays in this worker's context, not the orchestrator's (FR-005).

## Definition

- File: `.claude/agents/fix-mismatch.md`
- Frontmatter: `name: fix-mismatch`, `tools: Bash, Read, Edit, Write, Skill, Glob, Grep`,
  `model: inherit`, a `color`, and a `description` stating it runs the speckit workflow to fix a
  classification false-positive and opens a human-gated PR. Optionally run with worktree isolation so
  parallel fixes don't collide.

## Input (from the orchestrator)

- The `false` **Mismatch** row + its `root_cause` (`area`, `hypothesis`) from the verdict.
- The `period` and the affected `document_id`(s), so the fix can be verified by a scoped re-analyze.

## Procedure (in the agent body)

1. **Branch off `main`** (never work on `main` directly; never on the orchestrator's branch).
2. **Run the spec-driven workflow** via the `speckit` skill to design and implement the fix targeting
   the hypothesized `area`:
   - `reading` → the page-classification prompt/skill or field extraction.
   - `rollup-precedence` → `build_document_analysis` roll-up ordering in `documentos.py`.
   - `grouping` → `nf_groups.py` content-hash grouping.
   - `reconciliation-tolerance` → `nf_groups.reconcile_group` thresholds.
3. **Verify** the fix locally where feasible: re-run the scoped chain
   (`docs-plan`/classify/`apply-extractions`/`analyze`/`mismatches`) for the affected documents and
   confirm the false mismatch is gone without introducing new ones in scope. Run `pnpm lint` /
   `pnpm format` if TS is touched (none expected for analysis-only fixes).
4. **Open a PR** with `gh` (title references the mismatch + root cause; body links the period/doc and
   summarizes the change). **Do not merge. Do not push to `main`.**
5. **Return** ONLY a terse result.

## Output (the agent's entire return value)

```jsonc
{
  "mismatch_key": "2025-12|amount|<doc>|<entry>",
  "branch": "00X-fix-…",
  "pr_url": "https://github.com/…/pull/NN",   // null if it stopped before opening a PR
  "status": "pr-open",                          // pr-open | failed  (never "merged")
  "summary": "One line: what changed and why it fixes the false mismatch."
}
```

## Boundaries (non-negotiable)

- **Human-gated**: opens a PR; NEVER merges, force-pushes, or pushes to `main` (FR-008/SC-005).
- Returns only the terse result — no diffs, transcripts, or page content (FR-005/SC-002).
- Touches application/pipeline code only on its own fix branch; never edits the period JSON or the
  verdicts file (the CLI owns those).
- One mismatch (or one shared root cause) per invocation.
