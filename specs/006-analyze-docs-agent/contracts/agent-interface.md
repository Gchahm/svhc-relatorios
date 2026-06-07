# Contract: `analyze-docs` agent interface

The agent lives at `.claude/agents/analyze-docs.md` (a Claude Code subagent). It is invoked inside a
Claude Code session, typically delegated to by an orchestrator.

> **Evolution note:** this agent originally did the vision itself (read each page image and wrote a
> single `<period>.extractions.json`). It is now the **context-isolated vision/analysis step**: it
> delegates page reading to the `classify-doc-page` / `classify-period` skills, runs the deterministic
> pipeline, and hands back only a terse mismatch summary. The per-page reading + the
> `<image>.classify.json` contract now live with `classify-doc-page` (see
> `.claude/skills/classify-doc-page` and `contracts/extractions.schema.md`).

## Frontmatter

```yaml
---
name: analyze-docs
description: >-
    The context-isolated VISION/ANALYSIS step. Runs document-classification analysis for a whole
    scraped period OR a specified subset of documents, and returns ONLY a terse mismatch summary.
    Delegates page reading to the classify-doc-page / classify-period skills (never reads page images
    itself), then runs the deterministic merge + checks.
tools: Bash, Skill, Read, Glob
model: inherit
color: blue
---
```

`Bash` runs the pipeline commands; `Skill` invokes `classify-period`; `Read`/`Glob` inspect the
manifest/results. It does **not** read page images — that is delegated to the skills.

## Inputs

- A **period** (`YYYY-MM`) — required.
- Optionally a **subset**: `--document-id`(s) and/or `--entry-id`(s) to analyze instead of the whole
  period (so a re-run after a fix is cheap). Subset scoping is threaded through `docs-plan`.

## Procedure (defined in the agent body)

1. **Plan (scoped).** Run `docs-plan --periodo <period> [--document-id …] [--entry-id …]` to write
   the (scoped) manifest. Targeting ids implies re-analysis of those documents. If it reports
   "Nothing to extract", skip step 2.
2. **Classify (delegate).** Invoke the `classify-period` skill for the period — it reads the manifest
   and fans pages out to `classify-doc-page`, which writes the `<image>.classify.json` files. The
   agent never reads page images itself.
3. **Merge.** Run `apply-extractions --periodo <period>`.
4. **Check.** Run `analyze --periodo <period>`.
5. **Summarize.** Run `mismatches --periodo <period> [--document-id …] [--entry-id …]` and return that
   JSON as the entire result.

## Guarantees / boundaries

- The agent orchestrates and summarizes; it never reads page images, writes `.classify.json`, edits
  code/schema, or writes the period JSON by hand. `apply-extractions` is the only writer of
  `document_analyses`.
- Each representative page is classified once; byte-identical siblings are handled by the
  deterministic fan-out (SC-005).
- The hand-back is only the terse mismatch summary — no images, transcripts, or full artifacts —
  keeping the caller's context clean. Deciding true-vs-false and any fix are separate steps
  (feature `007-classification-improve-loop`).
