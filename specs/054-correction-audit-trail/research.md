# Research: Data-correction audit trail + reversibility

**Feature**: 054-correction-audit-trail | **Date**: 2026-06-13

All Technical-Context unknowns were resolvable from the existing codebase + the design doc
(`docs/features/false-positive-triage-agent.md`). No external research needed. Decisions below.

## D1 — Where does the durable correction store live?

- **Decision**: A new analysis-owned D1 table `data_corrections`.
- **Rationale**: The issue requires a *durable, human-visible, queryable, reversible* store. The
  three design-doc candidates (Q3): (a) the `<period>.verdicts.json` cache is gitignored ephemeral
  scratch — fails durability (US3); (b) `alerts.notes` is free-text on a different entity, not
  queryable/attributable per-correction — fails FR-002/FR-006; (c) a dedicated table is durable,
  queryable, and naturally analysis-owned (consistent with the mirror invariant: analysis derives
  into its own tables, never the scraper mirror). Mirrors the precedent set by `attachment_state`,
  `page_classifications`, `documents`/`document_entries`, `alerts` — all analysis/derived tables with
  their own Drizzle definition + migration.
- **Alternatives rejected**: verdicts.json (not durable), alerts.notes (not queryable), reusing the
  verdicts taxonomy (conflates code-fix verdicts with data corrections — explicitly forbidden by the
  design §4.4 / US3-AC2).

## D2 — The correction primitive (how a value is actually changed)

- **Decision**: Reuse the existing staging path. apply-correction (1) snapshots the attachment's
  current `page_classifications` rows, (2) writes the corrected per-page extraction(s) via the same
  validation gate `record_classification` enforces, (3) `mark-pending`s the attachment and runs a
  scoped `apply-extractions` (feature 050 staging-driven — only groups whose representative has
  staging are rolled up, so exactly this attachment's group is touched), then `build_documents` +
  `analyze` (scoped to the affected period) to refresh documents + alerts.
- **Rationale**: Decision D2 in the design says "the agent records the *verified* value via
  `record-classification`" — deterministic, not a blind re-vision. Feature 050 made `apply` staging-
  driven precisely so a single-attachment correction is non-destructive + self-scoping. Building a
  parallel write path would duplicate the roll-up/fan-out/reconciliation logic and risk drift.
- **Alternatives rejected**: directly UPDATE-ing `attachment_analyses` (bypasses the deterministic
  roll-up, sibling fan-out, group reconciliation, and the `documents` rebuild — would desync derived
  state); a new "blind re-vision" (could repeat the misread — design D2 forbids it).

## D3 — What "from" state is captured, and how rollback/undo restores it

- **Decision**: Snapshot the attachment's pre-correction `page_classifications` rows (the full set
  for that attachment, including `{"error": ...}` rows) into the correction record(s). Restore =
  re-write that exact snapshot to the staging table (delete the attachment's staging rows, insert the
  snapshot), then re-run the same scoped propagation (`mark-pending` → `apply-extractions` →
  `build-documents` → `analyze`). This deterministically reproduces the prior `attachment_analyses`.
- **Rationale**: `attachment_analyses` is a *pure derived roll-up* of the staging rows (via
  `D1ExtractionProvider` + `build_attachment_analysis` + `_merge_and_write`). Restoring the staging
  input and re-deriving is guaranteed to reproduce the prior analysis byte-for-byte (SC-002), with no
  guessing. Capturing the staging snapshot (not the rolled-up analysis) keeps restore on the same
  code path as apply — the inverse operation, symmetric and testable.
- **Edge — empty pre-state**: if the attachment had NO staging rows before (e.g. it was never
  classified, or staging was pruned), the snapshot is empty; restore writes an empty staging set,
  marks pending, and leaves the attachment pending (apply skips it — feature 050). That is the exact
  prior state, so it is correct.
- **Alternatives rejected**: snapshotting the rolled-up `attachment_analyses` row directly and
  re-inserting it (would diverge from the derive path — siblings/documents wouldn't be consistently
  rebuilt; and a future roll-up logic change would make the stored snapshot wrong).

## D4 — Field-level vs page-level record granularity

- **Decision**: Record **one `data_corrections` row per changed field**, with a shared
  `correlation_id` (the apply-correction call's id) so all rows from one call list/undo together. The
  underlying staging write still replaces the whole page extraction object (record-classification is
  page-level), but the audit captures `{field, from, to}` per changed field for human legibility.
- **Rationale**: The issue lists `field, from, to` as required record fields — a human auditing "what
  changed" wants the field-level diff, not "the whole 10-field object was rewritten." Computing the
  per-field diff (current page extraction vs corrected page extraction) is cheap and pure.
- **Alternatives rejected**: one row per page with a JSON blob of all fields (loses the from→to
  legibility the issue asks for); one row per call (can't attribute which field changed).

## D5 — Verify-after scope + the pass/fail rule

- **Decision**: Verify-after reads `summarize_mismatches` scoped to the **affected attachment ids**
  (the corrected attachment + its shared-NF siblings) BEFORE and AFTER the correction. PASS iff
  (a) the **targeted finding key** is present in the BEFORE set and ABSENT from the AFTER set, AND
  (b) the AFTER set introduces **no finding key absent from the BEFORE set** for that scope. Else
  FAIL → rollback. If the targeted finding key is not in the BEFORE set, the correction is
  **unverifiable** and is NOT applied (fail-closed, FR-010) — caught before any data change.
- **Rationale**: `summarize_mismatches` is the single-source finding detector already used by the
  alert checks and the review loop (no parallel logic — design §3). Scoping by attachment id keeps
  verify-after cheap and avoids false "new finding" from unrelated period churn. The finding "key" is
  the same stable identity `verdicts.mismatch_key` already computes from a summary row, so the agent
  and verify-after speak the same language.
- **Note**: `document_overpayment` findings are global (cross-period) and their `page_refs` resolve
  via the linked entries' attachments; verify-after includes them when the targeted/affected scope
  touches that document. The before/after sets are computed with the same scope so the comparison is
  apples-to-apples.
- **Alternatives rejected**: whole-period before/after (noisy — unrelated re-derivations would look
  like "new findings"); re-implementing finding detection (drift risk).

## D6 — Atomicity & the analysis-owned / mirror invariant

- **Decision**: All `data_corrections` writes go through `d1.upsert_tables`/`execute_sql`. The
  staging restore (delete attachment's staging + insert snapshot) is one atomic `execute_sql` batch
  (feature 024 convention). The correction never writes the mirror tables (`entries`/`attachments`/
  `accountability_reports`); it only writes the analysis-owned `data_corrections`, `page_classifications`,
  and triggers the existing analysis-owned writebacks (`attachment_analyses`, `attachment_state`,
  `documents`, `alerts`). The `from`-snapshot is read once up front; a verify-after failure restores it.
- **Rationale**: Matches every existing analysis writeback (features 024/026/035). The whole
  apply-correction is "snapshot → mutate → verify → (commit | restore)"; because restore is a
  deterministic re-derive from the snapshot, the only window of inconsistency is internal to one
  apply-correction call and is closed by either the verified commit or the rollback before the call
  returns.

## D7 — Status lifecycle

- **Decision**: A correction record has a `status` in {`applied`, `rolled-back`, `flagged`,
  `reverted`}. apply-correction writes `applied` (verify passed), `rolled-back` (verify failed,
  restore succeeded), or `flagged` (verify failed AND restore failed — needs a human). undo-correction
  transitions `applied` → `reverted` (restore succeeded) and is rejected for any non-`applied` status
  (FR-008). Status transitions are guarded in pure functions (unit-tested).
- **Rationale**: The four states cover every outcome the issue + edge cases name; `flagged` is the
  "couldn't verify and couldn't cleanly roll back" escape hatch (Edge: rollback failure) so a bad
  state is never silently `applied`.

## D8 — Idempotence (FR-012)

- **Decision**: The apply-correction call id is `det_id("data_correction_batch", attachment_id,
  target_finding_key, canonical(corrected_pages))`; the per-field record id is `det_id(
  "data_correction", batch_id, page_label, field)`. Re-applying the identical correction yields the
  same ids ⇒ `INSERT OR REPLACE` overwrites the same rows (no duplicate), and since the corrected
  staging equals the already-applied staging the field-diff is empty ⇒ no-op (FR-009). So a replay is
  both id-stable and data-stable.
- **Rationale**: Deterministic ids are the project-wide idempotence idiom (`det_id` everywhere). The
  no-op guard (FR-009) and the id-stability (FR-012) together make replay safe.

## Constitution re-check (post-design)

Unchanged from the plan's gate: PASS on all five principles. One table + migration (Principle I via
`pnpm db:generate`); all D1 via `d1.py` (Principle II); tests requested by spec, added as stdlib
unittest + integration (Principle III); CLI-only, `--remote` explicit (Principle IV); reuses existing
seams, one new module (Principle V). No violations.
