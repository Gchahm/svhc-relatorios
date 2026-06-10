---
model: inherit
description: >-
    Classify a scraped period's PENDING fiscal documents by deriving the work plan from the database and fanning each representative page out to the classify-doc-page skill in parallel, producing one `<image>.classify.json` per page. It runs `docs-plan` itself (which prints the plan as JSON to stdout — no manifest file). The set of attachments to classify is the pending set in D1 (`classified_at IS NULL`); to (re)classify a subset, mark those attachments pending first (`mark-pending`). Use it for "classify the attachments for 2025-12".
argument-hint: "[period] [--remote]"
allowed-tools: Bash, Read, Glob, Skill
context: fork
agent: general-purpose
disable-model-invocation: false
---

# Purpose

Orchestrate per-page classification for a scraped period's **pending** attachments. You own getting the work plan — you run `docs-plan` yourself, which derives the plan from the database and prints it as JSON to stdout (there is no manifest file) — and then you delegate the actual page reading to the `classify-doc-page` skill. You do not read images yourself, and you do not merge results into the database (`apply-extractions` does that, run by your caller). After you finish there is one `<image>.classify.json` next to every representative page image in scope.

# Input

`$ARGUMENTS` is a period in `YYYY-MM` form (the first token), optionally followed by:

- `--remote` — read the production D1 + R2 (default local). Forward it to every command below.

Example: `2025-12`.

**Scope is controlled in the database, not by flags.** The plan is the period's *pending* set (`attachments.classified_at IS NULL`). To (re)classify only specific attachments, the caller marks them pending first with `python -m analysis mark-pending --attachment-id <ids…>` (which clears `classified_at`); you then just classify whatever `docs-plan` reports as pending.

# Workflow

1. **Get the plan (run `docs-plan` yourself).** From `scripts/`, run docs-plan for the period and capture its **stdout**:

   ```bash
   cd scripts && uv run python -m analysis docs-plan --periodo <period> [--remote]
   ```

   This reads the period from D1, materializes the pending attachments' page images from R2 into the local cache, and **prints the plan as a JSON list of per-period envelopes to stdout** (no file is written — the shared-NF grouping comes from `attachments.content_hash`). Progress text goes to stderr, so stdout is pure JSON. If stdout is `[]` (docs-plan logs **"Nothing to extract"** — everything is already classified), there is nothing to classify — report that and stop.

2. **Parse the plan from stdout** and gather every page across each envelope's `groups[].pages[]`, using each page's absolute `read_path` (a materialized local cache image). These are only the *representative* pages of each shared-NF group; byte-identical siblings are handled by the deterministic merge downstream, so do not classify them.

3. **Delegate classification, in parallel.** For each collected page, invoke the **`classify-doc-page`** skill (via the Skill tool) with that page's `read_path` as its argument. Dispatch many at once — issue multiple Skill calls in a single turn — so pages are classified concurrently. Each invocation reads one image and writes `<image>.classify.json` next to it, self-validating through its own hooks. You do not inspect or post-process the per-page results.

4. **Confirm completeness.** After the batch returns, check (with Glob) that every page from the plan now has a sibling `.classify.json`. Re-dispatch `classify-doc-page` for any page still missing one.

5. **Report.** State how many pages were classified for the scope, and that the next step — the deterministic merge — is `cd scripts && uv run python -m analysis apply-extractions --periodo <period> [--remote]` (run by your caller).

# Boundaries (non-negotiable)

- You run `docs-plan` (getting the plan is yours) but you never merge: you never write `attachment_analyses` to D1 — `apply-extractions` is the only writer of the analyses.
- You never read the page images or write `.classify.json` files yourself — `classify-doc-page` does that.
- Classify only the representative pages listed in the plan; never re-classify byte-identical siblings.
