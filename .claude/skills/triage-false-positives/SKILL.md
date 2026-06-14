---
description: >-
    The thin batch orchestrator that scrubs document-vision false positives from a whole period (or a finding filter) BEFORE a human reviews. It lists candidate documents read-only via the `mismatches` CLI, fans out one context-isolated `fix-document-findings` agent per candidate document in parallel (each views that one document's page image(s) in its OWN context, autonomously data-corrects demonstrable misreads via the audited verify-after-gated path, and returns terse JSON), then aggregates the results into a single summary — corrected N / left M findings (by reason) / escalated K systematic faults. Coordination only: it holds no page images, runs no corrections or classification itself, and never merges code or touches `main`. Use it for "triage the false positives for a period (e.g. `<YYYY-MM>`)" or "scrub all open amount mismatches for a period".
argument-hint: "[period] [--kind k…] [--entry-id id…] [--remote]"
allowed-tools: Task, Bash, Read, Glob
---

# Purpose

Scrub the document-vision noise off a period's findings queue **before a human reviews it**, by
fanning the per-document correction work out to context-isolated workers and **coordinating only**.
You delegate every heavy step (viewing page images, judging findings, correcting data) to a
`fix-document-findings` agent and read back only terse JSON. Keeping your own context flat is a hard
requirement (SC-002): you **never** open a page image, run a correction/classification/analysis
command, inspect an artifact, or do ad-hoc SQL. Your only deliverable is one aggregated summary.

This is a **fraud/forgery audit tool**: leaving a false positive is safe; hiding a real finding is
not. The workers obey that rule; you simply report what they did and never override them.

# Input

`$ARGUMENTS`: a period in `YYYY-MM` form (first token), optionally followed by:

- `--kind <kind…>` — keep only findings of these kinds (`amount` / `vendor` / `date` / `page-error` /
  `document_overpayment`). Repeatable. Omitted ⇒ all kinds. Applied as a filter over the `mismatches`
  output.
- `--entry-id <id…>` — scope to these entries; forwarded to the `mismatches` CLI's native
  `--entry-id`.
- `--remote` — operate on production D1 + R2 (default **local**). Thread it to BOTH the `mismatches`
  listing AND every dispatched agent. Never write production implicitly.

Pipeline commands run from the repo's `scripts/` directory.

# Procedure

### 1. List candidates (read-only)

Run the `mismatches` CLI — never ad-hoc SQL, and never `classify` / `apply-extractions` / `analyze`
to "refresh" first (you triage what is already on the books):

```bash
cd scripts && uv run python -m analysis mismatches --periodo <period> [--entry-id <id…>] [--remote]
```

Parse the JSON array. Each row is one open finding. **Do NOT open any `page_refs` image** — you read
only the identifying fields. Then build the distinct candidate set:

- If `--kind` was given, drop every row whose `kind` is not in the set.
- A **`document_overpayment`** row is a **document candidate**: id = `row.document_id`; remember its
  `row.attachment_ids` (the document's source attachments).
- A **per-attachment** row (`amount` / `vendor` / `date` / `page-error`) is keyed by
  `row.attachment_id`. **Fold it into a document candidate when that attachment id appears in any
  document candidate's `attachment_ids`** — the document candidate's evidence already covers that
  attachment's findings, so it must not also spawn a separate candidate (avoids a duplicate dispatch
  AND a bare attachment id the evidence resolver can't open). Otherwise it is an **attachment
  candidate**: id = `row.attachment_id`.
- **De-duplicate by candidate id** — several findings on one attachment/document collapse to ONE
  candidate (the agent judges all of a candidate's findings in one pass; never fan out per finding).
- Tag each candidate `document` or `attachment` (you pass this hint to the agent so it knows which
  evidence resolver to use).

If the candidate set is **empty** → skip straight to Report with a zero-candidate "nothing to triage"
summary. Dispatch no agent (FR-009).

### 2. Fan out — one agent per candidate, in parallel

Dispatch **exactly one** `fix-document-findings` agent per distinct candidate, via the Task tool,
**all in a single message** (parallel fan-out — SC-003). Each agent's prompt:

> Triage the false positives on this candidate and return ONLY your terse JSON result.
> Candidate id: `<candidate_id>` (a **`<document|attachment>`** id). Target: **LOCAL** _(or
> "production — thread `--remote` through every command" when `--remote` was passed)_.
> For a **document** candidate, gather evidence with `document-evidence --id <candidate_id>`. For an
> **attachment** candidate (no built document), gather evidence with `mismatches --attachment-id
> <candidate_id>` instead, then judge and correct each finding via `apply-correction --attachment-id
> <candidate_id>` exactly as for a document.

The agent views the page image(s) in its OWN context, corrects only demonstrable misreads through the
audited `apply-correction` path, and returns `{document_id, attachment_ids, corrections[],
left_as_finding[], escalated[], note?}`. Keep each result terse; do not expand it, and do not open any
image yourself.

### 3. Aggregate + Report

Collect every agent's terse JSON and sum element-wise into one summary (counts MUST equal the sum of
the agents' results — SC-004):

- **candidates** — the number of agents dispatched.
- **corrected** — `Σ len(result.corrections)`.
- **left for human** — `Σ len(result.left_as_finding)`, broken down by `reason`: `true` /
  `page-error` / `verify-failed` / `unverifiable` / `no-op`, plus **`agent-error`** (see error rule).
- **escalated** — flattened `Σ result.escalated`, each listed as `{candidate, area, hypothesis}` for
  the human / the code-fix path.

Print one concise summary block (period, candidate count, corrected count, left-by-reason counts,
escalated list). That summary is your entire output — never paste page images, transcripts, or full
agent artifacts.

# Error isolation

If a dispatched agent **errors, times out, or returns un-parseable output**, count that candidate
under "left for human" with reason **`agent-error`** and continue aggregating the rest. One bad agent
NEVER aborts the batch (FR-008 / SC-005) — the worst case is one document left un-triaged for the
human, which is the safe direction for a fraud tool.

# Boundaries (non-negotiable)

- **Delegation only.** Every image read, judgment, and correction happens inside a
  `fix-document-findings` agent. You handle ids + terse JSON; you never open a page image
  (`page_refs`), run `classify` / `apply-extractions` / `apply-correction` / `analyze` / `reclassify`,
  or write D1/R2 — in your OWN context (SC-002).
- **Read-only listing.** Candidates come from the `mismatches` CLI; you do not re-classify or
  re-derive analyses before listing. The findings on the books are the work queue; re-running the
  skill later re-reads a naturally shrunk set.
- **One agent per candidate**, de-duplicated by candidate id; fan out in parallel; never per finding.
- **Findings preserved.** You report what the workers decided; you NEVER fix a finding yourself or
  override a worker's `true` / `page-error` verdict.
- **Human-gated code fixes.** Escalated systematic faults are reported for the human / the
  `improve-classification` path — you NEVER merge code or push to `main`.
- **Thread the target.** Default LOCAL; pass `--remote` to BOTH the `mismatches` listing and every
  agent only when explicitly told to. Never write production implicitly.
- **Always reports.** Even with zero candidates or all-errored agents, end with a summary; never
  abort silently.
