---
model: inherit
description: >-
    Classify a scraped period's fiscal documents (or a specified subset) by ensuring the work manifest exists and fanning each representative page out to the classify-doc-page skill in parallel, producing one `<image>.classify.json` per page. It runs `docs-plan` itself to (re)generate the manifest, scoped to the period and any document/entry ids you pass. Use it for "classify the documents for 2025-12" or "classify documents X and Y".
argument-hint: "[period] [--document-id <ids…>] [--entry-id <ids…>]"
allowed-tools: Bash, Read, Glob, Skill
context: fork
agent: general-purpose
disable-model-invocation: false
---

# Purpose

Orchestrate per-page classification for a whole scraped period or a chosen subset of its documents. You own getting the work manifest in place — you run `docs-plan` yourself — and then you delegate the actual page reading to the `classify-doc-page` skill. You do not read images yourself, and you do not merge results into the database (`apply-extractions` does that, run by your caller). After you finish there is one `<image>.classify.json` next to every representative page image in scope.

# Input

`$ARGUMENTS` is a period in `YYYY-MM` form (the first token), optionally followed by scope flags to narrow the run:

- `--document-id <id…>` — only these documents.
- `--entry-id <id…>` — only documents for these entries.

Examples: `2025-12` (whole period) · `2025-12 --document-id 1cad144b… f24a0995…` (just those two).

# Workflow

1. **Ensure the manifest (run `docs-plan` yourself).** From `scripts/`, run docs-plan for the period, passing through any scope flags from `$ARGUMENTS`:

   ```bash
   cd scripts && uv run python -m analysis docs-plan --periodo <period> [--document-id <ids…>] [--entry-id <ids…>]
   ```

   This writes/overwrites `data/scrape/<period>.extract-todo.json` scoped to what was asked. Passing `--document-id`/`--entry-id` re-plans those documents even if already analyzed (targeting implies re-analysis). If docs-plan reports **"Nothing to extract"**, there is nothing to classify — report that and stop.

2. **Read the manifest** `data/scrape/<period>.extract-todo.json` and gather every page across `groups[].pages[]`, using each page's absolute `read_path`. These are only the *representative* pages of each shared-NF group; byte-identical siblings are handled by the deterministic merge downstream, so do not classify them.

3. **Delegate classification, in parallel.** For each collected page, invoke the **`classify-doc-page`** skill (via the Skill tool) with that page's `read_path` as its argument. Dispatch many at once — issue multiple Skill calls in a single turn — so pages are classified concurrently. Each invocation reads one image and writes `<image>.classify.json` next to it, self-validating through its own hooks. You do not inspect or post-process the per-page results.

4. **Confirm completeness.** After the batch returns, check (with Glob) that every page from the manifest now has a sibling `.classify.json`. Re-dispatch `classify-doc-page` for any page still missing one.

5. **Report.** State how many pages were classified for the scope, and that the next step — the deterministic merge — is `cd scripts && uv run python -m analysis apply-extractions --periodo <period>` (run by your caller).

# Boundaries (non-negotiable)

- You run `docs-plan` (manifest creation is yours) but you never merge: you never write the period JSON or `document_analyses` — `apply-extractions` is the only writer of the analyses.
- You never read the page images or write `.classify.json` files yourself — `classify-doc-page` does that.
- Classify only the representative pages listed in the manifest; never re-classify byte-identical siblings.
