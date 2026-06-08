# Feature Specification: Self-Improving Document-Classification Loop

**Feature Branch**: `007-classification-improve-loop`
**Created**: 2026-06-07
**Status**: Draft
**Input**: User description: "A self-improving fiscal-document classification system driven by a thin orchestrator that loops: run analysis → review mismatches (true vs false) → delegate a speckit fix for false mismatches → repeat. First slice is a context-isolated vision step that reuses the classify-doc-page/classify-period skills and can run on a full period or a subset of documents."

## Overview

Document classification (reading fiscal page images into structured fields) is imperfect: each run
produces **mismatches** — cases where the extracted values disagree with the ledger entry (amount,
vendor, date) or trip a fraud check (e.g. duplicate billing). Some mismatches are **real findings**
(the document genuinely disagrees with the books — exactly what the product exists to surface).
Others are **the system's own fault** (a misread page, a wrong roll-up precedence, a grouping or
reconciliation bug).

This feature builds a loop that continuously drives down the *system's-fault* mismatches while
preserving the *real* ones. A thin **orchestrator** repeats: run the classification analysis →
review each mismatch as true or false → for false ones, delegate a fix that improves the system →
re-run. Every heavy step (vision over many pages, reading mismatch evidence, running the fix
workflow) is delegated to a **separate, context-isolated worker** that hands back only a terse
result, so the orchestrator's own context stays small and the loop can run many iterations.

The first and highest-priority slice is the **vision/classification step** itself, rebuilt to reuse
the existing classification skills and to run on a **subset of documents** (not only a whole
period), so each loop iteration is cheap.

## Clarifications

### Session 2026-06-08

- Validation: **US1 (the vision/classification step) is already implemented** — the `analyze-docs`
  agent (`.claude/agents/analyze-docs.md`) delegates to the `classify-period` → `classify-doc-page`
  skills, accepts `--document-id`/`--entry-id` subset targeting (threaded through `docs-plan`,
  `apply-extractions`, and the `mismatches` summary in `scripts/analysis/`), drives the deterministic
  merge + checks, and returns only a terse mismatch summary. FR-001–FR-003 and FR-005 are satisfied;
  this branch builds on it. **FR-004 gap**: the existing `mismatches` summary omits the **page
  reference(s)** the requirement calls for — so this branch extends `summarize_mismatches` to include
  `page_refs` (closing FR-004), which the review worker then consumes directly.
- Q: Who performs the true-vs-false mismatch review (US2)? → A: An **automated Claude-vision agent**
  (a separate context-isolated worker) reads the page image(s) + ledger entry and emits the verdict,
  so the loop can run unattended — no human-in-UI review step.
- Q: Where/how are verdicts and loop state stored? → A: **JSON working files per period** alongside
  the period data (e.g. `data/scrape/<period>.verdicts.json` plus a loop-state file); **no D1 schema
  change**.
- Q: For a false mismatch, how far does the fix worker go before the human gate? → A: It runs the
  full speckit pipeline on a branch and **opens a PR, but never merges** — merge stays human-gated.
- Q: Delivery scope of this feature branch (007)? → A: **US2 + US3 together** — build both the review
  step and the autonomous orchestrator loop in this branch (US1 already done).

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Context-isolated vision step over a full period OR a subset (Priority: P1) 🎯 MVP

A maintainer (or the orchestrator) asks for the classification analysis of either a whole scraped
period or a specific set of documents. The vision step reuses the existing per-page / per-period
classification skills to produce the per-page classifications, runs the deterministic merge and
checks, and returns a **concise mismatch summary** — without flooding the caller's context with page
images or intermediate files.

**Why this priority**: Nothing else in the loop can run or be tested until step 1 exists and returns
a usable summary; and making it run on a *subset* is what keeps every later iteration cheap. It is
independently valuable on its own (a fast, scoped "analyze these documents" capability).

**Independent Test**: Invoke the vision step for (a) a full period and (b) an explicit list of
document/entry ids; confirm in both cases it produces the per-page classifications, the
`document_analyses` are written, and it returns a terse machine-readable mismatch summary — and that
the subset run only processes the named documents, not the whole period.

**Acceptance Scenarios**:

1. **Given** a period with downloaded page images, **When** the vision step runs for that period,
   **Then** each representative page gets its classification (reusing the existing classify skills),
   the deterministic merge + checks run, and a summary of mismatches is returned to the caller.
2. **Given** a list of specific document (or entry) ids, **When** the vision step runs scoped to
   them, **Then** only those documents are (re)classified and analyzed — the rest of the period is
   untouched — and a mismatch summary for just those is returned.
3. **Given** a completed vision-step run, **When** the caller inspects what it received, **Then** it
   is a compact summary (per mismatch: document id, kind, ledger value vs extracted value, page
   references, any alert), not the page images or full intermediate artifacts.

---

### User Story 2 - Review a mismatch as true vs false (Priority: P2)

For each mismatch surfaced by step 1, a reviewer — an **automated, context-isolated Claude-vision
agent** (not a human-in-UI step) — looks at the actual evidence — the page image(s) plus the ledger
entry — and decides whether it is a **true mismatch** (the document really disagrees with the books —
a finding to keep and surface) or a **false mismatch** (the system misread or mis-reconciled). For a
false mismatch it records a root-cause hypothesis (which part of the system is wrong: the reading,
the roll-up precedence, the grouping, the reconciliation tolerance, etc.). The verdict is persisted
as a JSON working record per period (see Key Entities / Assumptions), with no database schema change.

**Why this priority**: This is the judgment the loop turns on; without it the system cannot tell a
real finding from its own bug. It depends on step 1's summary existing.

**Independent Test**: Feed the reviewer a known true mismatch and a known false mismatch (with their
images + entries); confirm it labels each correctly and, for the false one, returns a plausible
root-cause hypothesis.

**Acceptance Scenarios**:

1. **Given** a mismatch where the document's printed amount really differs from the ledger, **When**
   reviewed, **Then** it is labelled **true** (a finding) and is **not** queued for a system fix.
2. **Given** a mismatch caused by the system misreading a legible value, **When** reviewed, **Then**
   it is labelled **false** with a root-cause hypothesis pointing at the responsible part of the
   pipeline.
3. **Given** a mismatch that disappears simply by re-reading the page, **When** reviewed, **Then** it
   is distinguished from a systematic flaw (a transient misread that a re-run resolves, not a
   code-fix candidate).

---

### User Story 3 - The self-improving loop (Priority: P3)

A thin orchestrator ties it together: run step 1 → review mismatches (step 2) → for each false
mismatch, delegate a fix (step 3) that runs the spec-driven workflow to improve the system → loop
back to step 1 (scoped to the affected documents) until only true mismatches remain, or a stop
condition is hit. The orchestrator only coordinates and tracks minimal state; it does not do the
heavy work itself, and proposed fixes are **human-gated** (a fix may be prepared / a PR opened, but
nothing is auto-merged).

**Why this priority**: This is the end goal, but it is only safe and useful once steps 1 and 2 are
solid; it also carries the most risk (autonomous code changes), so it ships last.

**Independent Test**: Run the orchestrator on a period seeded with one known false mismatch; confirm
it detects the mismatch, reviews it as false, delegates a fix proposal, re-runs scoped to the
affected document, and terminates when no false mismatches remain — without auto-merging the fix.

**Acceptance Scenarios**:

1. **Given** a run that surfaces only true mismatches, **When** the orchestrator reviews them,
   **Then** it stops (converged) and reports the findings without attempting any fix.
2. **Given** a false mismatch, **When** the orchestrator processes it, **Then** it delegates a fix
   proposal and re-runs step 1 **scoped to the affected documents**, not the whole period.
3. **Given** a fix that does not resolve its mismatch (or a recurring mismatch), **When** the loop
   would repeat, **Then** a stop condition (max iterations / no-progress) halts it instead of looping
   forever.
4. **Given** any iteration, **When** the orchestrator delegates a step, **Then** it receives only a
   terse result, and its own context does not accumulate page images, diffs, or full artifacts.

### Edge Cases

- **Nothing to analyze** (period already fully classified, or an empty subset): the vision step
  reports "nothing to do" rather than failing.
- **A page cannot be classified** (missing/illegible image): surfaced as a per-page error, not a
  fabricated value, and treated by the reviewer as its own category (not a "true" finding).
- **Non-deterministic re-reads**: re-running classification may change a value; the loop must not
  treat normal re-read variation as endless new work (see US2 scenario 3 and US3 stop conditions).
- **A fix introduces a regression** elsewhere: a later iteration's mismatch set may grow; the loop's
  no-progress / max-iteration guard must still terminate.
- **Subset targeting includes a document with no images**: skipped with a recorded reason.
- **Conflicting verdicts across iterations** (a mismatch flips true/false between runs): treated as a
  no-progress signal for that item rather than re-fixing repeatedly.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The vision step MUST reuse the existing classification skills (per-page and per-period)
  to read page images — it MUST NOT introduce a separate, parallel vision/extraction implementation.
- **FR-002**: The vision step MUST accept either a full period or an explicit subset of documents
  (by document or entry id) and, for a subset, MUST process only those documents — leaving the rest
  of the period untouched.
- **FR-003**: The vision step MUST produce the per-page classifications in the existing format and
  drive the existing deterministic merge and checks, so its output is consumed by the rest of the
  pipeline with no schema change.
- **FR-004**: The vision step MUST return a **concise, machine-readable mismatch summary** to its
  caller — per mismatch: document id, mismatch kind (amount / vendor / date / duplicate-billing /
  page-error), ledger value vs extracted value, page reference(s), and any alert — and MUST NOT
  return page images or full intermediate artifacts.
- **FR-005**: Each heavy step (vision, review, fix) MUST run in its own delegated/context-isolated
  worker so the orchestrator's context does not grow with the volume of documents or pages processed.
- **FR-006**: The review step MUST be performed by an **automated, context-isolated Claude-vision
  worker** (no human-in-UI step) that decides, per mismatch, **true** (a real finding — surfaced,
  never "fixed") vs **false** (a system fault), using the page image(s) and the ledger entry as
  evidence, and MUST attach a root-cause hypothesis to a false mismatch. The verdict MUST be
  persisted as a JSON working record per period (no D1 schema change).
- **FR-007**: The review step MUST distinguish a transient misread (resolved by re-classifying) from
  a systematic flaw (requiring a code fix).
- **FR-008**: For a false mismatch, the fix step MUST be delegated to a separate worker that runs the
  spec-driven (speckit) workflow to improve the system. The worker MUST take the fix through the full
  pipeline on a branch and **open a PR**, but fixes MUST remain **human-gated** — the loop MUST NOT
  auto-merge to the main branch.
- **FR-009**: The orchestrator MUST loop run → review → fix → re-run, with re-runs after the first
  iteration **scoped to the affected documents**, and MUST terminate on convergence (no false
  mismatches remain), a maximum-iteration cap, or a no-progress condition.
- **FR-010**: True mismatches MUST be preserved and reported as findings across iterations; the loop
  MUST NOT attempt to "fix" them or suppress them.
- **FR-011**: The orchestrator MUST retain only minimal state between iterations (open mismatches,
  their verdicts, iteration count) and MUST NOT perform the vision, review, or fix work directly.

### Key Entities *(include if feature involves data)*

- **Mismatch**: one discrepancy from a classification run — its document, kind, ledger-vs-extracted
  values, page reference(s), and any associated alert. The unit the loop operates on.
- **Mismatch summary**: the terse, machine-readable list of mismatches handed from the vision step to
  its caller (the loop's working set).
- **Verdict**: the review outcome for a mismatch — true | false | transient | page-error — plus, for
  false, a root-cause hypothesis naming the suspect part of the pipeline. Persisted as a per-period
  JSON working record (e.g. `data/scrape/<period>.verdicts.json`); no D1 schema.
- **Fix proposal**: the delegated, human-gated change produced for a false mismatch — taken through
  the full speckit pipeline on a branch and surfaced as an **open PR** (never auto-merged), targeting
  the hypothesized root cause.
- **Loop state**: the orchestrator's minimal record — open mismatches, verdicts, iteration count,
  and progress markers used for the stop conditions — held in a per-period JSON loop-state working
  file alongside the period data.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: The vision step can analyze a specified subset of documents in time/cost roughly
  proportional to the subset size, **without** processing the whole period (a subset of K documents
  does not re-run the other documents in the period).
- **SC-002**: The orchestrator's working context does not grow with the number of documents/pages
  processed — it never directly holds page images or full intermediate artifacts, only terse
  summaries/verdicts.
- **SC-003**: For identical inputs, the deterministic parts of the run (merge + checks) yield the
  same mismatch set, so the loop's working set is reproducible given the same classifications.
- **SC-004**: Every true mismatch present at the start of a run is still reported as a finding at the
  end (none are silently dropped or "fixed").
- **SC-005**: The loop always terminates — it converges (no false mismatches) or halts on the
  max-iteration / no-progress guard — and never auto-merges a fix to the main branch.
- **SC-006**: After the first iteration, a re-run only re-classifies the documents implicated in the
  remaining mismatches.

## Assumptions

- The vision step is the evolution of the earlier single-file `analyze-docs` agent: it **reuses** the
  `classify-doc-page` and `classify-period` skills (which already exist and write
  `<image>.classify.json`) rather than re-implementing extraction; the deterministic `docs-plan` →
  classify → `apply-extractions` → `analyze` chain stays the source of truth. Subset runs build on
  the existing document/entry-id targeting in `docs-plan`.
- "Run analysis" in step 1 means the full chain that surfaces mismatches: classification → merge
  (`apply-extractions`) → checks (`analyze`).
- The fix loop is **human-gated** (it may open PRs but never auto-merges), and re-runs after the
  first iteration are scoped to affected documents — both per the maintainer's direction.
- A reasonable default stop policy applies (a small max-iteration cap and a no-progress guard on
  recurring mismatch ids); exact thresholds are an implementation/tuning detail.
- Mismatch and verdict records are working artifacts (alongside the period data) — concretely,
  per-period JSON files such as `data/scrape/<period>.verdicts.json` and a loop-state file — not new
  database schema; surfacing findings continues to flow through the existing `alerts` mechanism.
- The true-vs-false review (US2) is automated by a context-isolated Claude-vision worker, not a human
  UI step; this branch (007) delivers both US2 (review) and US3 (orchestrator loop) on top of the
  already-implemented US1 vision step.
