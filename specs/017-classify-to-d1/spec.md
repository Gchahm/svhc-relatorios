# Feature Specification: Remove `.classify.json` — classify-doc-page writes per-page extractions to D1

**Feature Branch**: `017-classify-to-d1`  
**Created**: 2026-06-10  
**Status**: Draft  
**Input**: GitHub issue [#22](https://github.com/Gchahm/svhc-relatorios/issues/22) — "Remove .classify.json — classify-doc-page writes per-page extractions to D1"

## Context (problem being solved)

In the document-classification pipeline, the vision skill (`classify-doc-page`) reads ONE page
image and today writes its extracted fields to a `<image>.classify.json` file in the ephemeral
cache. The deterministic `apply-extractions` step then reads those files (via
`FileExtractionProvider`) and persists each page's parsed result into the database
(`attachment_analysis_records.response`).

So the per-page vision result **already lands in the database** at apply time — the
`.classify.json` file is only a **pre-apply staging seam** between the Claude skill (which has
file tools) and the Python apply step. This file seam has two costs:

1. **Lost work on a cleared cache** — clearing the cache between classify and apply silently
   discards completed vision work, because `apply` reads *only* the files, never the database.
2. **Duplication** — the same per-page data exists as a file input and (after apply) as database
   output.

Issue #21 (already shipped) removed the `extract-todo.json` work-plan manifest, making the plan
DB-derived. This feature collapses the remaining file seam so per-page vision output lives in the
database too.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Vision output survives a cleared cache (Priority: P1)

A maintainer (or the analyze-docs agent / improve-classification loop) classifies a period's
pending attachments, then — for any reason (a separate machine, a cleaned scratch dir, a later
session) — the ephemeral cache no longer holds the per-page results. They run the deterministic
merge step. The merge still produces the correct `attachment_analyses` and alerts, because each
page's extraction was persisted to the database when it was classified, not left in a scratch
file.

**Why this priority**: This is the core defect the feature fixes — completed vision work must not
be silently discarded by clearing scratch. It also removes a class of confusing, hard-to-diagnose
"my analysis came back empty" failures.

**Independent Test**: Classify a period's pending attachments; delete every per-page scratch
artifact (keep only the materialized page images, which are reproducible from R2); run the merge
step; confirm the resulting `attachment_analyses` rows + alerts are equivalent to a run where the
scratch was never cleared.

**Acceptance Scenarios**:

1. **Given** a period whose pending pages have all been classified, **When** the per-page scratch
   artifacts are removed and the merge step is run, **Then** the merge reads the per-page
   extractions from the database and writes the same `attachment_analyses` + alerts as if the
   scratch had been kept.
2. **Given** a page that was never classified, **When** the merge step runs, **Then** that page is
   recorded as a per-page error (not a crash), the attachment is not aborted, and it surfaces as a
   `page-error` mismatch exactly as before.

---

### User Story 2 - End-to-end classification is unchanged in outcome (Priority: P1)

An operator runs the full `classify → apply → analyze → mismatches` sequence for a period (locally
or against production). The set of analyses, matches/mismatches, and alerts produced is equivalent
to the prior file-based flow — the only difference is where per-page extractions are staged
(database instead of a file).

**Why this priority**: The change must be behavior-preserving for the auditing output. Any drift in
the analyses or alerts would corrupt the fiscal review the whole tool exists to support.

**Independent Test**: For a representative period, run the end-to-end sequence and compare the
`attachment_analyses` roll-up fields (document type, extracted amount, amount/vendor/date match,
issuer, etc.), the per-page records, and the emitted alerts against a baseline captured before the
change. They match (modulo legitimately-removed dead columns).

**Acceptance Scenarios**:

1. **Given** a period's pending attachments, **When** the operator classifies each representative
   page and runs the merge, **Then** each representative attachment's roll-up and per-page records
   are equivalent to the file-based flow, and byte-identical siblings are still fanned out from the
   representative (no re-classification).
2. **Given** a shared-NF group, **When** the period is analyzed, **Then** group reconciliation,
   the duplicate-billing over-claim alert, and the mismatch summary behave exactly as before.

---

### User Story 3 - The cache holds only reproducible image scratch (Priority: P2)

After this feature, the ephemeral cache holds only materialized page images (still needed so the
vision skill can read them) and the loop's verdicts working file — no per-page extraction files.
A developer inspecting the cache, or reasoning about the pipeline, no longer has to treat a
scratch file as a source of truth for vision output.

**Why this priority**: Simplification and correctness of the mental model; it is the visible end
state that confirms the file seam is gone, but it delivers value only once Stories 1–2 hold.

**Independent Test**: After a full classify+apply run, search the cache for per-page extraction
files; none exist. Search the codebase; nothing reads or writes them and the file-backed provider
is gone.

**Acceptance Scenarios**:

1. **Given** a completed classify+apply run, **When** the cache is inspected, **Then** it contains
   materialized page images (and possibly a verdicts file) but no per-page extraction files.
2. **Given** the codebase after this feature, **When** searched, **Then** no code path writes or
   reads `*.classify.json` and the file-backed extraction provider no longer exists.

---

### Edge Cases

- **A page is re-classified.** Recording a page's extraction a second time (e.g. a corrected read,
  or a loop re-queue) overwrites the prior stored extraction for that page rather than creating a
  duplicate — the latest extraction wins.
- **The skill emits an error result** (`{ "error": "<reason>" }`) for a blank/illegible/missing
  page. That error is persisted for the page and is surfaced by the merge as a per-page error /
  `page-error` mismatch, identical to the file-based behavior.
- **Malformed or contract-violating extraction.** The persistence step validates the extraction
  against the frozen field contract (the same contract the file validator enforced today) and
  rejects a non-conforming payload with a clear message, so the skill can correct and retry —
  validation moves from a file-write hook to the record step.
- **A page has no stored extraction at merge time** (never classified, or classification failed
  before recording). The merge records a per-page error for that page and continues; the
  attachment is not aborted.
- **Re-running the merge.** Re-running the merge for the same pending set yields the same result
  and does not depend on any scratch file surviving — the per-page extractions are read from the
  database.
- **Targeted re-classification.** Marking an attachment pending again (the SQL-controlled
  `mark-pending` path) and re-classifying overwrites its stored per-page extractions and produces a
  fresh roll-up, with no leftover state from the prior run.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The per-page classification step MUST persist each page's extracted fields (or its
  error result) directly to the database, keyed so that exactly one stored extraction exists per
  (attachment, page).
- **FR-002**: Re-recording a page's extraction MUST replace the prior stored extraction for that
  page (idempotent upsert — the latest extraction wins), not accumulate duplicates.
- **FR-003**: The persistence step MUST validate each extraction against the frozen page-field
  contract (the exact field set, allowed `papel_artefato` values, and amount/date typing the
  pipeline consumes today) and MUST reject a non-conforming payload with an actionable message so
  the classifier can correct and re-record. An error result (`{ "error": "<reason>" }`) is the one
  permitted alternative to a full fields object.
- **FR-004**: The merge step (`apply-extractions`) MUST read per-page extractions from the
  database (not from any file) and MUST otherwise preserve the existing deterministic behavior:
  per-page records, heterogeneity-aware roll-up, shared-NF group reconciliation, sibling fan-out,
  entry validation, write-back via delete-then-insert, and stamping the attachment as classified.
- **FR-005**: The merge step MUST NOT depend on any cache file surviving between classification and
  merge; given the database state alone, it MUST produce the correct analyses.
- **FR-006**: No code path may write or read `*.classify.json`, and the file-backed extraction
  provider MUST be removed. The cache after a run MUST contain only materialized page images (and
  the loop's verdicts file).
- **FR-007**: The classification orchestrator (per-period skill) MUST pass each representative
  page enough identity (the attachment and page it belongs to) for the per-page step to record its
  extraction to the correct (attachment, page) key, since the page image filename alone does not
  carry the attachment identity.
- **FR-008**: The orchestrator's completeness check MUST verify, from the database, that every
  planned representative page has a recorded extraction (re-dispatching any that do not), replacing
  the prior filesystem check for sibling files.
- **FR-009**: The dead `raw_response` column (on attachment analyses) and `raw_text` column (on
  per-page records) — unused since the local-VLM path was retired — MUST be removed via a committed
  database migration, and all code and UI references to them MUST be removed.
- **FR-010**: The end-to-end `classify → apply → analyze → mismatches` outcome (analyses, matches,
  alerts, mismatch summary) MUST be equivalent to the pre-change flow, aside from the legitimately
  removed dead columns.
- **FR-011**: All documentation and contracts describing the file seam MUST be updated to describe
  the database-backed flow: the `classify-doc-page` skill contract, the `classify-period` skill,
  the `analyze-docs` agent, `CLAUDE.md`, `scripts/README.md`, and `scripts/pipeline-flow.md`. The
  `review-mismatch` agent's boundary note that lists `.classify.json` MUST also be corrected.
- **FR-012**: Both targets MUST be supported: the per-page record step and the merge read/write the
  **local** store by default and the **production** store on explicit request, consistent with the
  rest of the pipeline.

### Storage shape — decision

The issue presents a decision point (its item 3): a **dedicated per-page staging store** vs.
**reusing the existing per-page analysis records** with a status field.

**Decision: a dedicated per-page staging store**, keyed by (attachment, page label), holding the
raw per-page vision output (the fields object, or an error) plus a recorded-at timestamp.

**Rationale**:
- The existing per-page analysis records are **produced by** the merge step. Reusing them as the
  classifier's *input* creates a read/write cycle on one store (the merge would read the same rows
  it later overwrites via delete-then-insert), which is fragile and easy to get wrong.
- A dedicated store cleanly separates the **raw per-page vision input** (written by the classifier,
  one row per page) from the **finalized roll-up output** (`attachment_analyses` +
  `attachment_analysis_records`, written by the merge). The merge's existing delete-then-insert of
  the output is untouched.
- It keeps the "authoritative analysis is the finalized roll-up" invariant the issue calls for: the
  staging store is an input the merge consumes, never the surfaced analysis.

The alternative (reusing analysis records with a status) is explicitly rejected for the read/write
cycle risk noted above.

### Key Entities *(include if feature involves data)*

- **Page classification (new staging entity)**: the raw per-page vision result for one page of one
  attachment. Identified by the (attachment, page label) pair (unique — one extraction per page).
  Holds the extracted fields object **or** an error reason, plus the page label/index and a
  recorded-at timestamp. Written by the per-page classification step; read by the merge step as its
  per-page extraction source. Not surfaced to end users — it is pipeline input, not the
  authoritative analysis.
- **Attachment analysis & per-page analysis record (existing)**: the authoritative, finalized
  roll-up the merge produces and the UI reads. Unchanged in role; loses the dead `raw_response` /
  `raw_text` columns.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: After classifying a period and removing all per-page scratch artifacts, the merge
  step produces analyses + alerts identical to a run where scratch was retained (0 differences in
  roll-up fields, per-page records, and alerts).
- **SC-002**: The end-to-end `classify → apply → analyze → mismatches` sequence for a representative
  period yields analyses and alerts equivalent to the pre-change baseline (0 unexpected
  differences, aside from the removed dead columns).
- **SC-003**: After a full run, the cache contains 0 per-page extraction files, and a codebase
  search finds 0 read/write references to `*.classify.json` and 0 references to the file-backed
  provider.
- **SC-004**: Re-recording a page's extraction yields exactly 1 stored extraction for that page
  (no duplicates), and the latest value is the one the merge uses.
- **SC-005**: The `raw_response` and `raw_text` columns no longer exist in the database after the
  committed migration is applied, and the app builds and runs with 0 references to them.
- **SC-006**: An extraction that violates the frozen field contract is rejected at record time with
  an actionable message; a conforming extraction (or a well-formed error result) is accepted.

## Assumptions

- The local-VLM extraction path remains retired; the only producer of per-page extractions is the
  Claude vision flow, which sets the structured fields (so `raw_text` / `raw_response` carry no
  data and are safe to drop).
- The per-page classification step runs with a shell available (it can call the project's analysis
  CLI), as the issue proposes; it no longer needs file-write tools for output.
- Page identity for recording comes from the work plan (which already lists each representative
  attachment and its pages); the page-image filename is named by entry, not attachment, so identity
  is supplied by the orchestrator rather than parsed from the filename.
- The page label derivation used by the plan and by the merge is the same function on the same page
  tokens, so the (attachment, page label) key written at record time matches the key the merge
  looks up.
- No production data depends on the dead columns; dropping them does not require a data backfill.

## Out of Scope

- Introducing the future real-"document" (NF/receipt) N:N-with-entries entity — unchanged and not
  part of this feature.
- Changing the frozen page-field contract itself (field names, allowed values) — it is preserved;
  only where the result is staged changes.
- Any change to scraping, image materialization from R2, the shared-NF grouping key, or the
  self-improving loop's verdict bookkeeping.
- UI changes beyond removing references to the dropped dead columns.

## Dependencies

- Issue #21 (DB-derived work plan; `extract-todo.json` manifest removed) — already shipped on
  `main`. This feature builds on the DB-derived plan.
