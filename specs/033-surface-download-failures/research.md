# Research: Surface partial attachment-download failures

## Decision 1 — How "failed this run" is determined (scraper side)

**Decision**: In `_scrape_periodo`, after the in-run download loop and the existing
`preserve_existing_attachment_cols` merge, an attachment is "failed this run" iff a download was
attempted for it (`download_docs=True` and it has an `external_document_id` / is in
`doc_download_tasks`) AND its `file_path` is still falsy (NULL/empty). The download loop already
collects `paths_by_id` from `download_entry_documents`; an attachment whose `external_document_id`
is absent from that map got no pages.

**Rationale**: The spec (FR-008, Assumptions) distinguishes "attempted-and-failed this run" (drives
status/count) from "has no stored pages right now" (drives the alert). Using the post-preserve
`file_path` for the count means an attachment that failed THIS run but whose prior successful pages
were preserved is correctly NOT counted as a failure — the preserve step already restored its pages,
so there is no missing evidence. This keeps the run-level count aligned with actual evidence loss.

**Alternatives considered**:
- Count purely from `paths_by_id` membership (ignoring preserve): rejected — would count an
  attachment as failed even when its prior pages were preserved, producing a false `partial`.
- Track at the `documentos.py` level: rejected — the runner already has the per-attachment row +
  the preserve result; keeping the decision in the runner (delegated to a pure helper) avoids
  threading state through the extractor.

## Decision 2 — Where the run-level signal lives

**Decision**: Record the count + failed attachment ids in the existing `scrape_runs.errors`
free-form notes channel (the `consistency_notes`/`parse_notes` accumulator), formatted as
`"N attachment(s) failed to download in <period>: <id>, <id>, …"` per affected period. No new
`scrape_runs` column.

**Rationale**: The issue suggests "record the count on the scrape_runs row"; the established
convention (features 029/030) for non-fatal run observations is the `errors` notes channel, which is
already queryable (`SELECT errors FROM scrape_runs …`). Adding a column would require a Drizzle
migration for a value that the notes channel already conveys, contradicting Principle V (simplicity)
and the issue's "queryable after the run" intent. A dedicated `download_failures` column is recorded
as a deferred follow-up in the spec/data-model.

**Alternatives considered**:
- New `scrape_runs.failed_download_count` integer + `failed_download_ids` text columns: rejected for
  this slice (migration overhead); noted as a deferred follow-up.

## Decision 3 — The `partial` status value

**Decision**: Add `partial` as a third terminal status. Status precedence: fatal `errors` →
`error`; else any failed download → `partial`; else `success`. Computed in `run_scrape`'s `finally`
where `status` is already derived from `errors`.

**Rationale**: FR-003 requires a status distinct from both `success` and `error`, with a fatal error
dominating. The DB column is `text(length: 20)` and consumers render it generically (the comment in
`fiscal.schema.ts` already lists `running, success, error` as free-form), so a new value needs no
schema or consumer change. The `running` initial value is unchanged.

**Alternatives considered**:
- Reusing `success` + relying only on the note: rejected — FR-003 explicitly wants a status signal a
  scheduled job can branch on without parsing the note text.
- Reusing `error`: rejected — would conflate a non-fatal partial download with a fatal failure and
  break the existing "fatal" semantics + the screenshot-on-error path.

## Decision 4 — The alert: scraper-emitted vs analysis-emitted

**Decision**: The alert (`attachment_not_downloaded`, `warning`) is emitted by the analysis pass —
a new `check_attachment_not_downloaded(period)` in `scripts/analysis/checks/attachments.py`, wired
into `run_advanced` — over every attachment in `period.attachments` whose `file_path` is falsy.

**Rationale**: Mirror invariant (feature 026): the scraper must not write the analysis-owned `alerts`
table. The analysis side already owns alerts and already loads `attachments` (with `file_path`) per
period (FR-006/FR-009). Emitting from `run_advanced` means the alert rides the existing per-period
delete-then-insert writeback in `run_analysis`, giving idempotency (deterministic id keyed on the
attachment) and self-clearing (the attachment drops out of the recomputed set once `file_path` is
present) with zero new writeback code (FR-007). It is also correct for attachments left missing by an
*earlier* run that the current run never touched — the alert reflects the persistent mirror state,
not the run that happened to fail (FR-008). The existing scrape-time reconciliation cascade-cleans
the alert if the whole attachment row later vanishes from the portal.

**Alternatives considered**:
- Scraper writes the alert directly (like reconcile/consistency do): those write `alerts` from the
  scraper too — but they are period-scoped findings the scraper owns end-to-end. Here the natural
  single source of truth is the mirror's `file_path` state, which the analysis pass already reads, so
  emitting there avoids duplicating the "is it missing?" decision and keeps the alert correct
  independent of which run last touched the attachment. Chosen for the single-source-of-truth +
  free-idempotency win.

## Decision 5 — Alert identity, type, severity, metadata

**Decision**: Mirror the sibling `check_attachment_mismatches` exactly:
- `type = "attachment_not_downloaded"`, `severity = "warning"`.
- `id = det_id("alert", period.period, "attachment_not_downloaded", attachment_id)` — stable per
  attachment per period.
- `metadata = {attachment_id, entry_id, external_document_id}` so the feature-018 alert deep-link
  (`affectedEntryIds = entry_ids ?? [entry_id]`) resolves the owning entry. `reference_period` is the
  period.

**Rationale**: Reuses the exact deep-link contract the frontend `AlertsClient` already parses (it
reads `entry_id`/`entry_ids` from metadata), so no UI change is needed — the alert is clickable to
the entry immediately. `warning` matches the audit weight of "missing evidence" (the related
`large_expense_no_attachment` is also non-critical; `attachment_page_error` is `info`, but a
*completely unfetchable* attachment is a stronger signal than an illegible page, so `warning`).

**Alternatives considered**:
- Severity `info`: rejected — an unfetchable receipt is a missing-evidence finding (issue calls it
  "audit-relevant"), warranting `warning` over the milder `info` used for legible-but-noisy pages.
- Severity `critical`: rejected — it is a data-completeness gap, not a confirmed over-claim; the
  critical tier is reserved for confirmed money findings (`document_overpayment`, `portal_row_vanished`).
