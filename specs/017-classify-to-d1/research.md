# Phase 0 Research: Remove `.classify.json` — per-page extractions to D1

All unknowns from the Technical Context resolved below. Each item: Decision · Rationale ·
Alternatives considered.

## R1. Storage shape for staged per-page extractions

**Decision**: A **dedicated D1 table `page_classifications`**, one row per (attachment, page label),
holding the raw per-page vision result (the fields object, or an error) plus page label/index and a
recorded-at timestamp.

**Rationale**:
- The existing per-page analysis records (`attachment_analysis_records`) are **produced by** the
  merge (`apply-extractions` → `_merge_and_write` → `d1.upsert_tables`, via delete-then-insert).
  Reusing them as the classifier's *input* makes the merge read the same rows it later deletes and
  re-inserts — a read/write cycle that is fragile and order-dependent.
- A dedicated input store keeps the invariant the issue calls for: the **finalized roll-up
  (`attachment_analyses` + records) stays the authoritative analysis**; the staging table is only
  the merge's input.
- The merge's existing write path is untouched, minimizing behavioral risk (FR-004/FR-010).

**Alternatives considered**:
- *Reuse `attachment_analysis_records` with a `status` column* (`raw` vs `finalized`). Rejected: the
  read/write cycle above, plus it overloads one table with two lifecycles and complicates the
  delete-then-insert semantics.
- *Keep a file but move it into D1-as-blob*. Rejected: that is the same file seam in a different
  store; it does not let the merge read from the authoritative DB shape.

## R2. How the per-page step learns which (attachment, page) it is recording

**Decision**: The orchestrator (`classify-period`) passes `attachment_id` and `page_label` to
`classify-doc-page` alongside the image path; `classify-doc-page` forwards them to
`record-classification`. The merge looks up extractions by the same (attachment_id, page_label).

**Rationale**:
- Page-image files are named by **entry** (`download_entry_documents` → `base_name = entry_id`,
  giving `<entry_id>[_docN][_pN].<ext>`), **not** by attachment. So the attachment id is *not*
  derivable from the image path; parsing it would be wrong.
- The work plan already carries the identity: `build_plan` emits, per group, the
  `representative_attachment_id` and, per page, `page_index`/`page_label`/`path`/`read_path`.
  `classify-period` parses that plan, so it can hand each `classify-doc-page` invocation the
  `(read_path, attachment_id, page_label)` triple.
- `page_label` is derived by `_page_label_from_path(token, idx)` in `build_plan`, and the merge
  (`build_attachment_analysis`) derives it with the **same function on the same tokens in the same
  order** — so the key written at record time matches the key the provider looks up.

**Alternatives considered**:
- *Resolve attachment_id from entry_id inside the CLI via a D1 join.* Rejected as unnecessary
  indirection: the orchestrator already has the attachment id from the plan; passing it is simpler
  and avoids a per-page DB round trip in the skill.
- *Rename page-image files to embed attachment_id.* Rejected: out of scope, touches the scraper and
  R2 keys, and the plan already provides identity.

## R3. Where extraction validation lives now

**Decision**: Move the frozen-contract validation into the `record-classification` CLI. The skill no
longer writes a file, so the PostToolUse `Write|Edit` hook (`validate_classify.py`) no longer fires;
remove that hook and script. The PreToolUse `Read` image guard (`validate_image.py`) stays.

**Rationale**:
- Validation must run at the new write point (the CLI). The CLI rejects a non-conforming payload
  with a non-zero exit + actionable stderr, so the skill model corrects and re-records (mirrors how
  the file hook fed errors back). (FR-003, SC-006.)
- The contract is identical (REQUIRED_KEYS, PAPEL_VALUES, STRING_OR_NULL, AMOUNT_KEYS, and the
  `{"error": ...}` alternative) — port the logic from `validate_classify.py` into
  `scripts/analysis/page_classifications.py:validate_page_fields` so there is one canonical
  validator in the analysis module.

**Alternatives considered**:
- *Keep `validate_classify.py` as a manual/edge validator.* Rejected: it references `.classify.json`
  and would be dead code (FR-006 forbids `.classify.json` references). The canonical validator lives
  in the analysis module where the CLI consumes it.

## R4. Orchestrator completeness check without files

**Decision**: `docs-plan` annotates each planned page with `recorded: true|false` (a left-join
against `page_classifications`). `classify-period` re-dispatches any page whose `recorded` is false,
replacing the prior `Glob` for sibling `.classify.json` files.

**Rationale**:
- The completeness signal must come from the DB now (FR-008). Adding `recorded` to the plan is a
  pure read at plan time and keeps `docs-plan` stdout pure JSON (no D1 write → no wrangler banner on
  stdout, preserving the constraint that `classify-period` parses stdout).
- Re-running `docs-plan` for the recheck is cheap: images are already materialized in the cache, so
  `materialize_period_images` is a near-no-op on the second call.

**Alternatives considered**:
- *A separate `classification-status` CLI.* Rejected as redundant: `docs-plan` already produces the
  page list; annotating it avoids a second command and a second code path that could drift.
- *Skip the check and let `apply` record per-page errors.* Rejected: the loop wants completeness
  before the merge so a missing page is re-dispatched, not silently surfaced as a `page-error`.

## R5. Loading staging rows for the merge

**Decision**: Extend `loader._load_period_raw` to query `page_classifications` for the period's
attachments and attach them as `raw["page_classifications"]` (decoding the stored JSON `response`
back to an object, mirroring how `attachment_analysis_records.response` is decoded). The
`D1ExtractionProvider` is built from that list (a `{(attachment_id, page_label): row}` map), so the
merge does **one** batched read per period, not a wrangler call per page.

**Rationale**:
- Consistent with how the loader already assembles the period `raw` dict (analyses, records,
  alerts). Keeps all D1 reads in the loader and the provider purely in-memory.
- One query per period avoids N subprocess `wrangler` invocations (performance + correctness).

**Alternatives considered**:
- *Query inside the provider per page.* Rejected: a `wrangler` subprocess per page is slow and
  noisy; batch-load once.

## R6. Dropping the dead `raw_response` / `raw_text` columns

**Decision**: Remove `attachment_analyses.raw_response` and `attachment_analysis_records.raw_text`
from the Drizzle schema and generate a committed migration (`pnpm db:generate`). Remove the Python
dataclass fields (`AttachmentAnalysisResult.raw_response`, `PageAnalysisRecord.raw_text`) and their
`to_dict`/fan-out copies, and the two UI references (the API route `select` and the detail dialog
fallback/render).

**Rationale**:
- Both columns are unused since the local-VLM path was retired; the Claude flow only ever sets
  `response` (confirmed by code search — the only writers/readers are the schema, the Python
  dataclasses' own plumbing, and the UI fallback). Safe to drop with no data backfill (FR-009,
  SC-005).
- D1/SQLite supports `ALTER TABLE ... DROP COLUMN`; Drizzle generates it from the schema diff.

**Alternatives considered**:
- *Leave the columns and just stop writing them.* Rejected: the issue explicitly requires removal
  via a committed migration; leaving dead columns is the duplication/confusion this feature removes.
- *Hand-write the migration SQL.* Rejected (constitution I): schema changes flow through
  `pnpm db:generate`.

## R7. CLI input shape for the extraction JSON

**Decision**: `record-classification` accepts the JSON via `--json` (inline string) **or** stdin
(when `--json` is omitted or is `-`). The skill uses a heredoc to pipe the JSON on stdin, avoiding
shell-quoting hazards for Brazilian names/accents/quotes.

**Rationale**:
- Inline JSON on a command line is fragile with embedded quotes/unicode; stdin via a quoted heredoc
  (`<<'JSON' … JSON`) is robust and is something the skill model can emit reliably.
- Supporting both keeps the command testable from the shell (inline) and ergonomic from the skill
  (stdin).

**Alternatives considered**:
- *Inline-only.* Rejected for the quoting hazard. *stdin-only.* Acceptable but slightly less
  convenient for manual testing; supporting both costs nothing.
