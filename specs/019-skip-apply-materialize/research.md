# Research: Skip R2 image materialization in apply-extractions

**Feature**: 019-skip-apply-materialize | **Date**: 2026-06-10

No `NEEDS CLARIFICATION` markers remained after specify (issue #27 is fully specified). The
research below confirms the design assumptions against the current code.

## Decision 1: Where the guard lives

- **Decision**: Add a predicate `attachments_needing_hash_backfill(periods, attachment_ids=None)`
  to `scripts/analysis/images.py`, and apply the detect-and-skip guard **inside
  `apply_extractions`** (`scripts/analysis/extractions.py`). Leave `materialize_period_images`
  unchanged.
- **Rationale**: Issue #27's decision point states the shared `materialize_period_images` must NOT
  change behavior for the classify (`docs-plan`/`build_plan`) and review (`summarize_mismatches`)
  callers, so the guard must be apply-specific. Co-locating the predicate in `images.py` (next to
  the materialization/hash logic it mirrors) keeps the "what needs a hash?" definition in one place
  and makes it independently testable, without altering `materialize_period_images`'s contract.
- **Alternatives considered**:
  - *Add a `skip_if_hashed` flag to `materialize_period_images`*: rejected — changes the shared
    function's surface and risks the classify/review callers depending on it later; the issue
    explicitly wants the shared function untouched.
  - *Inline the predicate directly in `apply_extractions` with no helper*: workable but the
    one-line list-comprehension is more testable and self-documenting as a named helper in
    `images.py` (where the symmetric hashing logic already lives).

## Decision 2: Definition of the "hashable-unhashed" set

- **Decision**: An attachment needs a backfill iff it has a non-empty `file_path` **and** a falsy
  `content_hash`. The set spans **all** loaded periods' attachments (not just the pending set).
- **Rationale**: `select_work` / `build_plan` group **all** page-bearing attachments in the period
  (`with_path = [d for d in period_data.attachments if d.get("file_path")]`) to compute sibling
  sums — so grouping reaches for `content_hash` (or the file-hash fallback) on every page-bearing
  attachment, not only pending ones. If any such attachment's `content_hash` is NULL, the fallback
  in `nf_groups._group_key` would hash its files and therefore needs them materialized. A page-less
  attachment (`file_path` empty) legitimately has no `content_hash`, groups as a singleton by id,
  and is never hashable — so it must be excluded from the set (issue acceptance criterion + spec
  US3/FR-004).
- **Alternatives considered**:
  - *Only consider pending attachments*: rejected — grouping touches all page-bearing attachments;
    a non-pending sibling with a NULL hash would still force a fallback hash and a missing image.
  - *Treat "NULL content_hash" alone as work (ignore file_path)*: rejected — would flag page-less
    attachments as work, re-introducing fruitless R2 lookups (issue's explicit warning).

## Decision 3: Scope the materialize call to the needing set

- **Decision**: When the set is non-empty, call
  `materialize_period_images(periods, cache_dir, target, attachment_ids=<needing ids>)` (default
  `backfill_hash=True`). When empty, skip the call and log a one-line skip.
- **Rationale**: `materialize_period_images` already supports an `attachment_ids` scope; passing
  only the needing ids downloads exactly the images required for the backfill and nothing else
  (FR-003). The other (already-keyed) attachments group from the `content_hash` column; the apply
  path never reads their image bytes (page labels derive from `file_path` token strings via
  `_page_label_from_path`, which parses the basename and works on R2-key tokens or local paths
  alike). Output parity therefore holds (FR-005).
- **Alternatives considered**:
  - *Materialize the whole period when any row needs it*: rejected — unnecessary downloads;
    scoping is free (the param exists) and matches FR-003.

## Decision 4: Maintenance command (`backfill-content-hash`)

- **Decision**: Out of scope (no new CLI command).
- **Rationale**: The lazy fallback already backfills any page-bearing attachment that lacks a
  `content_hash` on the next apply run (FR-007, self-correcting). Adding a one-off command is
  explicitly optional in the issue and violates nothing, but adds surface for no present need
  (constitution V — YAGNI).

## Verification of "apply reads no image bytes" (parity safety)

Confirmed by reading the code:

- `apply_extractions` → `build_plan` → `select_work` → `group_attachments` → `_group_key`: prefers
  `doc.get("content_hash")`; only falls back to `content_hash(file_path)` (which reads bytes) when
  the column is falsy.
- `build_attachment_analysis` uses `file_path` only to split tokens and derive `page_label`
  (`_page_label_from_path`); per-page fields come from the `provider` (`D1ExtractionProvider`),
  which reads the `page_classifications` rows loaded from D1. No file open.
- `_merge_and_write` issues SQL only.

So with every page-bearing attachment keyed, the guard skips materialize and **no** code path in
apply opens an image file → 0 R2 reads, identical output.
