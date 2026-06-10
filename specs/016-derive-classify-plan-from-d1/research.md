# Phase 0 Research: Derive the classification plan from D1

No `[NEEDS CLARIFICATION]` markers remained after specify. This file records the design
decisions and the alternatives weighed, so the implementation has no open unknowns.

## Decision 1 — Persisted grouping key uses the existing content-hash algorithm

**Decision**: Persist `attachments.content_hash` as the md5 produced by the current
`nf_groups.content_hash` (per-page byte hash, each page length-delimited with `:{size}:`, in
page order). Reuse the exact function so stored values equal what the plan computes today.

**Rationale**: FR-002 requires byte-identical grouping continuity. Re-implementing the hash
risks a subtly different value (e.g. omitting the size delimiter) that would silently re-group
attachments and change reconciliation outcomes. Reuse is the only safe option.

**Alternatives considered**:
- Hash without the size delimiter / different digest (sha256) — rejected: changes the value,
  breaks continuity, no benefit.
- Use `external_document_id` or extracted NF number as the key — rejected: the module docstring
  already explains these differ per sibling / are noisy; that is *why* content hashing exists.

## Decision 2 — Where the hash is computed at capture time

**Decision**: Compute the hash in the scraper from the **local downloaded page files**
(`paths_by_id[ext_id]`) right before/after R2 upload, in both `run_scrape` (`_scrape_periodo`)
and `run_download_docs`. Store it on the attachment row (`content_hash`).

**Rationale**: The scraper already has the bytes locally before upload (issue note). Hashing
there is free and makes the column populated for all freshly-captured data (SC-002). `file_path`
on the row holds R2 keys, not local paths, so the hash must be taken over the local files, not
`file_path`.

**Alternatives considered**:
- Compute from R2 after upload — rejected: needs an extra download; the bytes are already local.
- Compute lazily only in analysis — rejected: violates FR-001 ("populated when captured").

## Decision 3 — Shared helper location (preserve scraper/analysis decoupling)

**Decision**: Move the pure hashing helper into a new `scripts/common/hashing.py`. `nf_groups.py`
re-exports `content_hash` from there (keeping its public name/imports stable); the scraper imports
it from `common`.

**Rationale**: Feature 008 decoupled scraper and analysis: they share only `scripts/common`. The
scraper must not import from `analysis`. `common` already hosts the only cross-subsystem code
(`det_id`, `now_ms`); the hash is exactly that kind of shared leaf. `content_hash` is stdlib-only
(`hashlib`, `pathlib`), so it fits `common`'s stdlib-only contract.

**Alternatives considered**:
- Scraper imports `analysis.nf_groups` — rejected: re-couples the packages.
- Duplicate the function in the scraper — rejected: two copies of a correctness-critical hash
  drift apart; violates DRY and risks FR-002.

## Decision 4 — Plan is a pure function used by both plan and apply (no file)

**Decision**: Extract `build_plan(...)` returning the in-memory group/member structure. `docs-plan`
prints it as JSON to stdout; `apply-extractions` calls the same builder to re-derive groups from D1.
No `extract-todo.json` is written or read (FR-007).

**Rationale**: The manifest only existed to carry plan state between two CLI invocations. Since the
plan is a pure function of D1 + materialized images, each command can rebuild it deterministically.
A shared builder guarantees `apply` sees exactly the groups `plan` printed. `classify-period` reads
the printed JSON from stdout instead of a file.

**Alternatives considered**:
- Keep writing a file but in D1 instead of disk — rejected: re-introduces a stale-able intermediate,
  the very thing being removed.
- Have `apply` consume `docs-plan` stdout — rejected: couples the two invocations via a pipe and the
  classify step runs *between* them; independent re-derivation is simpler and order-independent.

## Decision 5 — Backward compatibility for NULL content_hash (existing data)

**Decision**: `group_attachments` prefers `doc["content_hash"]`; when NULL it falls back to computing
`content_hash(doc["file_path"])` over materialized cache files (today's behavior); when that also
fails, a `doc:{id}` singleton. Additionally, `materialize_period_images` lazily backfills the column
in D1 for NULL rows it has materialized.

**Rationale**: The local and prod DBs already hold ~100+ attachments with NULL `content_hash`. FR-009
requires equivalence on that data without a forced re-scrape (which needs portal credentials). The
fallback yields identical grouping immediately; the lazy backfill converges the data to pure-DB
grouping after one analysis run (SC-004).

**Alternatives considered**:
- Require a full re-scrape before the feature works — rejected: blocks shipping, needs portal access,
  and the issue explicitly wants continuity on existing data.
- One-shot backfill migration in SQL — rejected: the hash needs the actual page bytes, which SQL/D1
  cannot read; it must run in Python with materialized images.

## Decision 6 — Optional `classification_status` column NOT added

**Decision**: Do not add `classification_status` / `classified_at`. "Pending = no
`attachment_analyses` row" stays the definition of pending; targeted re-classification stays driven by
`--attachment-id`/`--entry-id`.

**Rationale**: The issue marks it optional. None of the acceptance criteria need it, targeting already
works, and adding columns + dirty-tracking is scope the spec consciously excludes (constitution V,
YAGNI). Can be revisited independently if a real need appears.

**Alternatives considered**:
- Add the column now — rejected: speculative, widens the migration + touches the loop bookkeeping for
  no required outcome.

## Verification approach (no test framework)

- **Hash continuity**: a Python check confirming `common.hashing.content_hash` over a known page set
  equals the value `nf_groups.content_hash` produced before the move (identical function → identical).
- **Grouping equivalence**: against the existing local period(s), assert the set of NF groups (and each
  group's members/sibling_sum/group_size) from the column-aware path equals the legacy file-hash path.
- **End-to-end**: run `docs-plan` (prints, writes no file) → `apply-extractions` → `analyze` →
  `mismatches` on a local period and diff `attachment_analyses` + alerts against a pre-change snapshot;
  confirm no `*.extract-todo.json` exists afterward.
