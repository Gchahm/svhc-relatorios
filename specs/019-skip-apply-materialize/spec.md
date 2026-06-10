# Feature Specification: Skip R2 image materialization in apply-extractions when no content_hash backfill is needed

**Feature Branch**: `019-skip-apply-materialize`  
**Created**: 2026-06-10  
**Status**: Draft  
**Input**: GitHub issue #27 — "apply-extractions: skip R2 image materialization when no content_hash backfill is needed"

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Steady-state apply makes no wasted R2 round-trip (Priority: P1)

An operator runs the apply step of the classification pipeline (`apply-extractions`) on a
database whose attachments were all scraped recently (every page-bearing attachment already
carries its shared-NF grouping key). Today, every run downloads the whole period's page
images from remote storage before doing any work — even though the apply step reads none of
those image bytes (per-page extractions come from the staging table, page labels come from
parsing stored paths, and grouping reads the stored grouping-key column). The operator wants
the apply step to skip that download entirely when there is nothing to backfill, so the step
is faster and does not touch remote storage for no reason.

**Why this priority**: This is the entire point of the feature — removing pure per-run
overhead from the most common case. Every other story is a safety guarantee around it.

**Independent Test**: On a database where every page-bearing attachment already has a
grouping key, run the apply step and confirm it performs zero image downloads while producing
exactly the same analysis output as before.

**Acceptance Scenarios**:

1. **Given** a period in which every page-bearing attachment already has a grouping key,
   **When** the operator runs the apply step, **Then** no page images are downloaded from
   remote storage and the run completes.
2. **Given** that same period, **When** the operator runs the apply step, **Then** the written
   analyses, shared-NF reconciliation, sibling fan-out, and amount/vendor/date match flags are
   identical to what the prior (always-materialize) behavior produced.

---

### User Story 2 - Legacy attachments without a grouping key still get backfilled (Priority: P2)

A page-bearing attachment was captured before the grouping-key column existed (or by some
future path that lands a page-bearing attachment without one), so its grouping key is empty.
The operator runs the apply step. The step must still bring that attachment's images local,
compute its grouping key, group it correctly, and backfill the stored key — exactly as it does
today — so the optimization is self-correcting and never degrades grouping.

**Why this priority**: Correctness guarantee. The optimization must not break the legacy /
edge case the materialize call exists to handle.

**Independent Test**: Clear the grouping key on one page-bearing attachment, run the apply step,
and confirm that attachment's images are fetched, its group is computed correctly, and its
stored grouping key is repopulated.

**Acceptance Scenarios**:

1. **Given** a page-bearing attachment whose grouping key is empty, **When** the operator runs
   the apply step, **Then** that attachment's images are materialized, it is grouped correctly
   with any byte-identical siblings, and its stored grouping key is backfilled.
2. **Given** a mix of attachments where most have a grouping key and a few do not, **When** the
   operator runs the apply step, **Then** only the attachments missing a key trigger an image
   fetch, and grouping/reconciliation across the whole set is correct.

---

### User Story 3 - Page-less attachments are never treated as work (Priority: P3)

An attachment legitimately has no page images (empty path) and therefore has no grouping key by
nature; it groups as a singleton. The optimization's "is there anything to backfill?" check must
treat such an attachment as nothing to do — never as a reason to reach for remote storage and
never as a hashable-but-unhashed row.

**Why this priority**: Prevents a false positive in the guard that would re-introduce the
overhead this feature removes (and would fruitlessly look for images that don't exist).

**Independent Test**: On a database whose only attachment lacking a grouping key is a page-less
one, run the apply step and confirm it performs no image downloads.

**Acceptance Scenarios**:

1. **Given** an attachment with no page images (and thus no grouping key), **When** the operator
   runs the apply step, **Then** that attachment does not trigger an image fetch and the run
   performs no downloads (assuming all page-bearing attachments already have a key).

---

### Edge Cases

- **All page-bearing attachments already keyed (normal case)**: guard finds nothing to do →
  skip remote storage entirely; grouping reads the stored key column.
- **A page-bearing attachment missing its key**: guard includes it → materialize (scoped to the
  attachments that need it) and backfill it.
- **A page-less attachment (empty path)**: never counts as work for the guard; groups as a
  singleton; no fetch attempted.
- **An attachment whose key is missing AND whose remote image is also missing**: the existing
  behavior is preserved — a clean per-page error is recorded downstream; the run is not aborted.
- **Multiple periods loaded at once**: the guard considers all loaded periods' attachments; if
  any page-bearing attachment anywhere in scope lacks a key, materialization runs for the rows
  that need it.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The apply step MUST NOT download any page images from remote storage when every
  page-bearing attachment in scope already has a grouping key.
- **FR-002**: The apply step MUST still materialize images for, compute the grouping key of, and
  backfill the stored grouping key of any page-bearing attachment in scope whose grouping key is
  empty.
- **FR-003**: When materialization is performed for the backfill case, it MUST be limited to the
  attachments that actually need it (page-bearing and missing a key); attachments that already
  have a key MUST NOT cause downloads.
- **FR-004**: An attachment with no page images MUST be treated as "nothing to backfill" by the
  guard (it is not hashable and never needs a key), and MUST NOT trigger an image fetch.
- **FR-005**: The written attachment analyses (roll-up), per-page records, shared-NF
  reconciliation outcome, sibling fan-out, and amount/vendor/date/page-error match flags MUST be
  identical to the prior always-materialize behavior for the same input (output parity).
- **FR-006**: The change MUST be local to the apply step. The image-materialization behavior used
  by the plan/classify path and the mismatch-summary/review path MUST be unchanged — both still
  materialize their images.
- **FR-007**: The backfill fallback MUST remain self-correcting: a future run that encounters a
  page-bearing attachment without a key MUST repopulate it, so the database converges without
  manual intervention.
- **FR-008**: Documentation describing the apply step MUST be updated to reflect that it only
  reaches for remote storage when a grouping-key backfill is actually needed.

### Key Entities *(include if feature involves data)*

- **Attachment**: the per-entry page bundle. Relevant attributes: its page-image path list
  (empty for a page-less attachment) and its shared-NF **grouping key** (empty for legacy rows
  or page-less attachments). The grouping key is normally written at scrape time.
- **Hashable-unhashed set**: the in-scope attachments that are page-bearing **and** whose
  grouping key is empty — the only attachments that genuinely require image bytes during the
  apply step. When this set is empty, the apply step needs no remote-storage access.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: On a database where every page-bearing attachment has a grouping key, an apply run
  performs **0** page-image downloads (down from "all in-scope page images" today).
- **SC-002**: For the same period, the set of written analyses and their match flags is **100%**
  identical before and after the change (parity on the persisted analyses).
- **SC-003**: With one page-bearing attachment's grouping key cleared, an apply run repopulates
  that key and groups the attachment correctly — **100%** of such rows converge in a single run.
- **SC-004**: The plan/classify path and the mismatch-summary path still materialize their images
  (0 regressions in their image availability).

## Assumptions

- The shared-NF grouping key is persisted on the attachment at scrape time for all recently
  scraped data; the only attachments lacking it are legacy rows or page-less attachments.
- During the apply step, page-image bytes are required **only** to compute a missing grouping
  key. (Per-page extractions are read from the staging table; page labels are derived from stored
  path strings; grouping prefers the stored key column.)
- A page-less attachment legitimately has no grouping key and groups as a singleton; this is not
  an error and is not work for the guard.
- A one-off maintenance command to eagerly backfill grouping keys is **out of scope** — the lazy
  fallback already converges the database over normal runs.
