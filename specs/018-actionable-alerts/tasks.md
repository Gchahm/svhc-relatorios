# Tasks: Actionable Alerts — Drill-Down to Entry/Attachment Validation

**Feature**: `018-actionable-alerts` | **Spec**: [spec.md](./spec.md) | **Plan**: [plan.md](./plan.md)

Tests are OPTIONAL and not requested (no test framework — Constitution III). Verification is
manual + the CLI idempotency/agreement checks in [quickstart.md](./quickstart.md).

## Phase 1: Setup

- [ ] T001 Confirm no new dependencies are needed: verify `src/components/ui/popover.tsx`
  exists (multi-entry link list) and the analysis CLI runs (`cd scripts && uv run python -m analysis --help`). No installs.

## Phase 2: Foundational

_No cross-story blocking work. The shared mismatch module (T010) is scoped to US2; the
frontend deep-link plumbing (T005–T007) is scoped to US1. Stories are independently shippable._

## Phase 3: User Story 1 — Drill from an alert into the validation view (Priority: P1)

**Goal**: Every entry-level alert links to its affected entry/entries; clicking opens the
attachment-analysis detail dialog on the right period. Works for the EXISTING entry-level
alerts (`duplicate_billing`, `duplicate_entry`, `negative_credit`,
`large_expense_no_attachment`) and for any alert carrying `entry_id`/`entry_ids` in metadata.

**Independent Test**: On `/dashboard/alerts`, click an affected-entry link on an existing
entry-level alert → entries page opens on the correct period, row highlighted, detail dialog
auto-opened. Period/category-level alerts show no link.

- [ ] T002 [US1] Add `metadata: alerts.metadata` to the select in `src/app/api/alerts/route.ts`
  (per contracts/alerts-api.md); ordering and auth unchanged.
- [ ] T003 [US1] In `src/app/dashboard/alerts/AlertsClient.tsx`: add `metadata: string | null`
  to the `AlertRow` interface and a memoized parse helper
  `affectedEntryIds(row): string[]` = `meta.entry_ids ?? (meta.entry_id ? [meta.entry_id] : [])`,
  parsing `row.metadata` defensively (try/catch → `[]` on null/malformed).
- [ ] T004 [US1] In `src/app/dashboard/alerts/AlertsClient.tsx`: add an "Entries" column
  (header + body cell + matching footer spacer) to the virtualized table. Render per
  `affectedEntryIds`: 0 → `—`; 1 → an inline Next `<Link>` ("Open ↗"); >1 → a shadcn
  `Popover` trigger ("N entries") listing one `<Link>` per id. Each link/trigger calls
  `e.stopPropagation()` so it does not toggle the row's resolved state. Links target
  `/dashboard/entries?period=${row.referencePeriod}&entry=${id}` (contracts/deep-link.md).
- [ ] T005 [US1] In `src/app/dashboard/entries/EntriesClient.tsx`: read `useSearchParams()`
  for `period` and `entry`; when `period` is present set it as the initial `selectedPeriod`
  (override the `getCurrentPeriod()` default) on first mount only.
- [ ] T006 [US1] In `src/app/dashboard/entries/EntriesClient.tsx`: after the target period's
  entries + analyses finish loading, run a one-shot effect (guarded by a ref keyed on the
  `period|entry` param pair) that: resolves `analysisByEntry.get(entry)` and calls
  `setSelectedAnalysis(...)` to auto-open the dialog when found; scrolls the matching row
  into view via `virtualizer.scrollToIndex(idx, { align: "center" })` and applies a transient
  highlight; no-ops without error when the entry is absent or has no analysis (FR-008).
- [ ] T007 [US1] In `src/app/dashboard/entries/EntriesClient.tsx`: confirm closing the dialog
  (`onOpenChange(false)` → `setSelectedAnalysis(null)`) leaves `selectedPeriod` and the row
  intact and does NOT re-trigger the deep-link effect (US1.3).

**Checkpoint US1**: Existing entry-level alerts are clickable end-to-end; MVP deliverable.

## Phase 4: User Story 2 — Per-attachment document mismatches as their own alerts (Priority: P1)

**Goal**: `analyze` emits a clickable alert per (attachment, kind) for amount/vendor/date
mismatches and page-errors, sharing one detection source with the `mismatches` CLI (FR-004).
US1's AlertsClient already renders links for these (single `entry_id`).

**Independent Test**: For a period with a mismatching attachment, `analyze` then check
`/dashboard/alerts` shows `attachment_*_mismatch` / `attachment_page_error` alerts; their
count equals the `mismatches` CLI count (SC-004).

- [ ] T010 [P] [US2] Create `scripts/analysis/mismatches.py` (stdlib only): `KIND_*` constants,
  `AttachmentMismatch` dataclass, and `detect_attachment_mismatches(period, refs)` reading the
  persisted `attachment_analyses` match flags (per contracts/mismatch-detection.md). Imports
  only model/ref types (no cycle).
- [ ] T011 [US2] Refactor `scripts/analysis/extractions.py:summarize_mismatches` to build its
  per-attachment rows from `detect_attachment_mismatches(...)`, mapping each `AttachmentMismatch`
  to the existing row shape (`kind`, `ledger_amount`/`extracted_amount`,
  `ledger_vendor`/`extracted_issuer`, `expected_period`/`extracted_date`, `detail`) plus
  `page_refs`; keep the scoping filters and the unchanged `duplicate_billing` rows. Output
  shape MUST stay identical (loop/review-worker contract).
- [ ] T012 [P] [US2] Create `scripts/analysis/checks/attachments.py`:
  `check_attachment_mismatches(period, refs)` mapping each `AttachmentMismatch` to an `Alert`
  via the `_alert(..., discriminator=attachment_id)` pattern — types
  `attachment_amount_mismatch` / `attachment_vendor_mismatch` / `attachment_date_mismatch`
  (warning) and `attachment_page_error` (info); metadata
  `{attachment_id, entry_id, kind, ledger_value, extracted_value}` (+ `detail` for page-error);
  human-readable pt-BR title/description.
- [ ] T013 [US2] Wire `check_attachment_mismatches` into the orchestrator: call it from
  `scripts/analysis/checks/advanced.py:run_advanced` (alongside `check_duplicate_billing`,
  passing `refs`), so it runs in `run_all_checks` and writes through `analyze`'s
  delete-then-insert path.

**Checkpoint US2**: `analyze` produces per-attachment mismatch alerts; they appear with links.

## Phase 5: User Story 3 — Re-runs don't pile up duplicate alerts (Priority: P2)

**Goal**: Re-analyzing an unchanged period yields an identical alert set.

**Independent Test**: Run `analyze` twice for a period; alert ids/count identical.

- [ ] T014 [US3] Verify idempotency: the new alert ids are `det_id("alert", period, type,
  attachment_id)` (deterministic) and `analyze` deletes-then-inserts per `reference_period`.
  Run `uv run python -m analysis analyze --periodo <p>` twice and confirm the `alerts` rows
  for that period are byte-identical (ids + count). Fix the discriminator if any non-stable
  field leaked in.

## Phase 6: Polish & Cross-Cutting

- [ ] T015 [P] Update docs: `CLAUDE.md` (new alert types + linkage metadata + deep-link
  contract; note alert `resolved` vs loop verdicts independence — FR-011), `scripts/README.md`,
  and `scripts/pipeline-flow.md` (the new check in `run_all_checks`).
- [ ] T016 Run quality gates: `pnpm lint && pnpm format`; confirm no Python import cycle
  (`cd scripts && uv run python -c "import analysis, analysis.extractions, analysis.checks, analysis.mismatches"`).
- [ ] T017 Manual end-to-end verification per [quickstart.md](./quickstart.md): analyze a
  period, open `/dashboard/alerts`, click a single-entry mismatch link and a multi-entry
  `duplicate_billing` popover link, confirm the dialog opens on the right period/entry, and
  confirm a period-level alert shows no link.

## Dependencies & Execution Order

- **US1 (T002–T007)** is independent of US2 and is the MVP (links for existing alerts).
- **US2 (T010–T013)**: T011 and T012 both depend on T010; T013 depends on T012. T010/T012 are
  parallel-startable relative to each other only after T010's file exists — practically T010 →
  {T011, T012} → T013.
- **US3 (T014)** depends on US2 (T013) producing the alerts to re-run.
- **Polish (T015–T017)** after the stories it documents/verifies.
- US1 and US2 can be built in parallel by different people; they meet at the alerts page (US1
  renders links for whatever alerts exist, including US2's).

## Parallel Opportunities

- `[P]` T010 and T012 are distinct new files (after T010 exists, T012 can be written against
  its interface).
- `[P]` T015 (docs) is independent of code once T013 lands.
- The entire US1 frontend track (T002–T007) runs in parallel with the US2 Python track
  (T010–T013).

## Implementation Strategy

MVP = **US1** alone (existing entry-level alerts become clickable). Then **US2** adds the new
mismatch alert source (auto-clickable via US1). **US3** is a verification guarantee. Ship in
that order; each checkpoint is demoable.
