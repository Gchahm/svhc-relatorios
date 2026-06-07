---
model: inherit
description: >-
    Extract a whole scraped period's fiscal documents by classifying every representative page in parallel. It ensures the work manifest exists (a PreToolUse hook creates it via `docs-plan`), then delegates each page image to the `classify-doc-page` skill, producing one `<image>.classify.json` per page. Takes a period (YYYY-MM). Use it for requests like "classify the documents for 2025-12" or "extract document fields for this period".
argument-hint: [period]
allowed-tools: Read, Glob, Skill
context: fork
agent: general-purpose
disable-model-invocation: false
hooks:
  PreToolUse:
    - matcher: "Read"
      hooks:
        - type: command
          command: 'uv run --no-project python "$CLAUDE_PROJECT_DIR/.claude/skills/classify-period/scripts/ensure_manifest.py"'
---

# Purpose

Orchestrate per-page classification for an entire scraped period. You do **not** read images or extract fields yourself, and you do **not** write the database. Your job is to:

1. make sure the period's work manifest exists, and
2. fan the manifest's representative pages out to the `classify-doc-page` skill (in parallel),

so that after you finish there is one `<image>.classify.json` next to every representative page image. Planning (`docs-plan`) and the final merge (`apply-extractions`) are deterministic steps run outside this skill — manifest creation is handled for you by a hook.

## Input

`$ARGUMENTS` is a single period in `YYYY-MM` form (e.g. `2025-12`).

## Workflow

1. **Read the manifest** `data/scrape/<period>.extract-todo.json`. A PreToolUse hook (`scripts/ensure_manifest.py`) creates it via `docs-plan` if it is missing. If the hook blocks the read (e.g. nothing to extract because the period is already analyzed), relay its message and stop — do not try to create the manifest yourself.

2. **Collect the pages.** From the manifest, gather every page across `groups[].pages[]`. Use each page's absolute `read_path`. These are only the *representative* pages of each shared-NF group; byte-identical siblings are handled by the deterministic merge downstream, so do not classify them and do not deduplicate further.

3. **Delegate classification, in parallel.** For each collected page, invoke the **`classify-doc-page`** skill (via the Skill tool) with that page's `read_path` as its argument. Dispatch many at once — issue multiple Skill calls in a single turn — so pages are classified concurrently. Each invocation reads one image and writes `<image>.classify.json` next to it, self-validating through its own hooks. You do not inspect or post-process the per-page results.

4. **Confirm completeness.** After the batch returns, check (with Glob) that every page from the manifest now has a sibling `.classify.json`. Re-dispatch `classify-doc-page` for any page still missing one.

5. **Report.** State how many pages were classified for `<period>` and that the next step — the deterministic merge — is run by the maintainer: `cd scripts && uv run python -m scraper apply-extractions --periodo <period>`.

## Boundaries (non-negotiable)

- You never read the page images or write `.classify.json` files yourself — `classify-doc-page` does that. You never write the period JSON; `apply-extractions` is the only writer of the analyses.
- You never generate the manifest by hand or run `docs-plan` directly — the PreToolUse hook owns manifest creation.
- Classify only the representative pages listed in the manifest; never re-classify byte-identical siblings.
