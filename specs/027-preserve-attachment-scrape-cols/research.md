# Research: Preserve scraper-owned attachment columns across re-scrapes

## R1 — Root cause confirmation

**Decision**: The remaining clobber is `attachments.file_path` and `attachments.content_hash`.

**Evidence** (from the live codebase):
- `scripts/common/d1.py:_generate_inserts` emits `INSERT OR REPLACE INTO "attachments" (...)`.
  SQLite `REPLACE` deletes the conflicting row and inserts a fresh one, so any column absent from the
  row dict (or set NULL) reverts to its default (NULL).
- `scripts/scraper/runner.py` builds each attachment row as
  `{"id", "entry_id", "external_document_id", "file_path": None, "content_hash": None}` and only
  fills `file_path`/`content_hash` later **in the same run** if `download_docs` is set and the
  per-attachment download succeeds (the `if download_docs and doc_download_tasks:` block).
- Migration `drizzle/0012_clever_sir_ram.sql` (issue #33) moved `classified_at` to a new
  `attachment_state` table and dropped it from `attachments`; the comment states "content_hash stays
  on `attachments`". The scraper never writes `attachment_state`, so the classification-state half of
  BUG-001 is already fixed — confirmed by `scripts/tests/test_attachment_state.py`.

**Conclusion**: Only `file_path` and `content_hash` remain at risk on a re-scrape that omits (or
fails) the image download.

## R2 — Where to apply preservation

**Decision**: In the scraper's attachment write path (`runner.py`), not in the generic
`INSERT OR REPLACE` generator.

**Rationale**:
- `scripts/common/d1.py` is shared by every table (entries, alerts, analyses, …) and by both the
  scraper and the analysis pipeline. Changing its REPLACE semantics (e.g. to a column-merging
  `ON CONFLICT DO UPDATE`) would silently change every writer's behavior and is far larger blast
  radius than the bug warrants.
- The scraper already reads D1 at run start (`SELECT period FROM accountability_reports`), so a
  scoped `SELECT id, file_path, content_hash FROM attachments` for the period is the same access
  pattern and keeps the fix local.

**Alternatives considered**:
- *Generic `ON CONFLICT(id) DO UPDATE SET <non-null cols>` in `d1.py`*: rejected — too broad, would
  need per-table column allow-lists and would change semantics for tables that legitimately want a
  full replace.
- *A second targeted UPDATE after the upsert*: rejected — two writes instead of one, and a partial
  failure could leave the row in the nulled state (the atomic-writeback principle from feature 024
  prefers a single statement set; carrying values into the single upsert keeps it one write).

## R3 — Preservation rule

**Decision**: Per attachment id: for each of `file_path` and `content_hash`, if the freshly-scraped
value is NULL/empty and an existing non-NULL value is known for that id, use the existing value;
otherwise keep the freshly-scraped value (which wins when the download succeeded).

**Rationale**: Matches FR-001..FR-004. A NULL in the fresh row is exactly the signal that "this run
produced nothing newer"; a non-NULL fresh value is a successful re-download that must win (US2).
Decided per id so a partial download preserves the un-downloaded siblings while updating the
downloaded ones (FR-004, US-1 scenario 2).

**Edge**: empty string is treated like NULL for `file_path` (defensive — the scraper joins R2 keys
with `;`, so a real value is never empty; an empty string would itself be a loss). `content_hash`
preserves only on `None` (a hash is never an empty string in practice; treat falsy as "absent").

## R4 — Testing approach

**Decision**: Add `scripts/tests/test_attachment_preserve.py` (stdlib `unittest`) exercising the
pure merge helper directly, mirroring `test_attachment_state.py` (no live D1).

**Rationale**: The repo's Python tests are pure-function unit tests over importable seams; the live
D1 path is not unit-tested (it shells out to wrangler). Extracting the merge as a pure function makes
the rule directly assertable and is the project's established pattern.

**Coverage**: preserve-on-null, overwrite-on-fresh-value, per-id partial, NULL-stays-NULL when no
existing, new id (no existing) unaffected, existing-but-fresh-also-null stays null. (Maps SC-001,
SC-002, SC-004 and FR-001..FR-004, FR-007.)

## R5 — Manual verification approach

**Decision**: Verify against local D1 using the `verify` skill: seed a period's attachment with
non-NULL `file_path`/`content_hash`, run the scraper's merge against a simulated re-scrape (or a
direct `query` before/after) and confirm the values survive; confirm `attachment_state` rows are
untouched. The portal login is not available in the sandbox, so verification uses the local D1 data +
the pure helper / a scripted merge-and-upsert, recorded in the PR body.
