---
model: inherit
description: >-
    Classify a scraped period's PENDING fiscal documents by deriving the work plan from the database and fanning each representative page out to the classify-doc-page skill in parallel, which records one per-page extraction to the database per page. It runs `docs-plan` itself (which prints the plan as JSON to stdout — no manifest file). The set of attachments to classify is the pending set in D1 (`classified_at IS NULL`); to (re)classify a subset, mark those attachments pending first (`mark-pending`). Use it for "classify the attachments for a given period (e.g. `<YYYY-MM>`)".
argument-hint: "[period] [--remote]"
allowed-tools: Bash, Read, Glob, Skill
context: fork
agent: general-purpose
disable-model-invocation: false
---

# Purpose

Orchestrate per-page classification for a scraped period's **pending** attachments. You own getting the work plan — you run `docs-plan` yourself, which derives the plan from the database and prints it as JSON to stdout (there is no manifest file) — and then you delegate the actual page reading to the `classify-doc-page` skill, which records each page's extraction to the database. You do not read images yourself, and you do not merge results into the authoritative analysis (`apply-extractions` does that, run by your caller). After you finish, every representative page in scope has one recorded classification in the database (the plan reports each page's `recorded` flag).

# Input

**Classify the period given in `$ARGUMENTS`.** Use that exact period verbatim in every command below — do not substitute any other period (in particular, never use a period that appears only as an example in this document).

`$ARGUMENTS` is a period in `YYYY-MM` form (the first token, e.g. `YYYY-MM`), optionally followed by:

- `--remote` — read the production D1 + R2 (default local). Forward it to every command below.

**Scope is controlled in the database, not by flags.** The plan is the period's *pending* set (`attachments.classified_at IS NULL`). To (re)classify only specific attachments, the caller marks them pending first with `python -m analysis mark-pending --attachment-id <ids…>` (which clears `classified_at`); you then just classify whatever `docs-plan` reports as pending.

# Workflow

1. **Get the plan (run `docs-plan` yourself).** From `scripts/`, run docs-plan for the period and capture its **stdout**:

   ```bash
   cd scripts && uv run python -m analysis docs-plan --periodo <period> [--remote]
   ```

   This reads the period from D1, materializes the pending attachments' page images from R2 into the local cache, and **prints the plan as a JSON list of per-period envelopes to stdout** (no file is written — the shared-NF grouping comes from `attachments.content_hash`). Progress text goes to stderr, so stdout is pure JSON. If stdout is `[]` (docs-plan logs **"Nothing to extract"** — everything is already classified), there is nothing to classify — report that and stop.

2. **Parse the plan from stdout** and gather every page across each envelope's `groups[].pages[]`. For each page you need three things: its absolute `read_path` (a materialized local cache image), the group's `representative_attachment_id` (the attachment the page belongs to), and the page's `page_label`. These are only the *representative* pages of each shared-NF group; byte-identical siblings are handled by the deterministic merge downstream, so do not classify them.

3. **Delegate classification, in parallel.** For each collected page, invoke the **`classify-doc-page`** skill (via the Skill tool) passing the page's `read_path`, its `representative_attachment_id`, and its `page_label` as space-separated tokens (and a trailing `--remote` when you are running the period against production, so the page records to the production database). Dispatch many at once — issue multiple Skill calls in a single turn — so pages are classified concurrently. Each invocation reads one image and **records its extraction to the database** (the `page_classifications` staging table), self-validating through the `record-classification` CLI. You do not inspect or post-process the per-page results.

4. **Confirm completeness.** After the batch returns, re-run `docs-plan` for the period and check each page's `recorded` flag. Re-dispatch `classify-doc-page` for any page still showing `recorded: false` (no extraction was recorded for it). The plan derives `recorded` from the database, so this is the authoritative completeness check.

5. **Report.** State how many pages were classified for the scope, and that the next step — the deterministic merge — is `cd scripts && uv run python -m analysis apply-extractions --periodo <period> [--remote]` (run by your caller).

# Boundaries (non-negotiable)

- You run `docs-plan` (getting the plan is yours) but you never merge: you never write `attachment_analyses` to D1 — `apply-extractions` is the only writer of the authoritative analyses.
- You never read the page images or record classifications yourself — `classify-doc-page` reads each image and records its per-page extraction to D1.
- Classify only the representative pages listed in the plan; never re-classify byte-identical siblings.
