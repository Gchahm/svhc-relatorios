# Phase 1 Data Model: Self-Improving Document-Classification Loop

No database schema changes. These entities are **working artifacts** that flow between the loop's
workers as terse JSON and persist in `data/scrape/<period>.verdicts.json`. The source of truth for
documents/entries/analyses/alerts remains `data/scrape/<period>.json` (read-only here).

## Entity: Mismatch

One discrepancy surfaced by step 1 (`python -m analysis mismatches`). Consumed, not stored by this
feature — it is the existing output of `summarize_mismatches`.

| Field | Type | Notes |
|-------|------|-------|
| `period` | string (`YYYY-MM`) | always present |
| `kind` | enum | `amount` \| `vendor` \| `date` \| `page-error` \| `duplicate_billing` |
| `document_id` | string | present for per-document kinds; absent for `duplicate_billing` |
| `entry_id` | string \| null | the ledger entry, when resolvable |
| `document_ids` / `entry_ids` | string[] | present only for `duplicate_billing` (the shared-NF group) |
| `ledger_amount` / `extracted_amount` | number \| null | for `kind=amount` |
| `ledger_vendor` / `extracted_issuer` | string \| null | for `kind=vendor` |
| `expected_period` / `extracted_date` | string \| null | for `kind=date` |
| `detail` | string | for `kind=page-error` |
| `nf_total` / `sum_entries` / `over_claim` | number \| bool | for `kind=duplicate_billing` |
| `page_refs` | object[] | the page image(s) for the mismatch's document(s); each `{document_id, page_label, read_path}` (absolute `read_path` for the Read tool). For `duplicate_billing`, one group of refs per document in `document_ids`. Added to `summarize_mismatches` to close FR-004. |

**Mismatch identity** (the loop's join key — Decision 4): a deterministic key over the *stable*
fields only, excluding volatile extracted values:
- per-document kinds: `period | kind | document_id | entry_id`
- `duplicate_billing`: `period | kind | sorted(document_ids)`

## Entity: Verdict

The review worker's judgment about one Mismatch. One record per mismatch identity per iteration;
the latest is authoritative, prior ones retained as history.

| Field | Type | Notes |
|-------|------|-------|
| `mismatch_key` | string | the Mismatch identity (above) |
| `mismatch` | object | the originating Mismatch row, copied verbatim (for audit) |
| `verdict` | enum | `true` \| `false` \| `transient` \| `page-error` |
| `root_cause` | object \| null | **required when `verdict=false`**, else null |
| `root_cause.area` | enum | suspect pipeline part: `reading` \| `rollup-precedence` \| `grouping` \| `reconciliation-tolerance` \| `other` |
| `root_cause.hypothesis` | string | one or two sentences naming what is wrong and why |
| `confidence` | enum | `high` \| `medium` \| `low` — reviewer's certainty |
| `iteration` | integer | loop iteration in which this verdict was produced (≥ 1) |
| `reviewed_at` | string (ISO) | stamp written by the recording CLI |

**Validation rules**
- `verdict=false` ⇒ `root_cause` present with a non-empty `hypothesis` and a valid `area`.
- `verdict=true` ⇒ surfaced as a finding, never queued for a fix (FR-010).
- `verdict=transient` ⇒ eligible for at most one re-classification of its document, not a code fix
  (FR-007).
- `verdict=page-error` ⇒ recorded as a data-quality item, neither a finding nor a fix candidate.

**State transitions** (per mismatch identity, across iterations):
```
(new mismatch) → reviewed{true|false|transient|page-error}
false      → (fix PR opened) → re-analyzed → resolved (mismatch gone) | still-open (recurs)
transient  → (re-classified once) → resolved | recurs-as-no-progress
true       → finding (terminal; reported every iteration)
page-error → data-quality (terminal; reported, not fixed)
any        → flipped (verdict differs from a prior iteration) ⇒ no-progress signal for that id
```

## Entity: FixProposal

The human-gated change the fix worker produces for a `false` mismatch. Not stored in the verdicts
file beyond a reference; the authoritative artifact is the Git branch + PR.

| Field | Type | Notes |
|-------|------|-------|
| `mismatch_key` | string | the false mismatch it targets |
| `branch` | string | the fix branch the worker created |
| `pr_url` | string \| null | the opened PR (null if the worker stopped before opening one) |
| `summary` | string | one-line description of the change |
| `status` | enum | `pr-open` \| `failed` — never `merged` (human gate; the loop never merges) |
| `iteration` | integer | iteration that produced it |

**Invariant**: `status` is never `merged` — merging is exclusively a human action (FR-008/SC-005).

## Entity: LoopState

The orchestrator's minimal record, computed deterministically by `loop-state` and persisted in the
verdicts file. The orchestrator reads it; it does not maintain it by hand (FR-011).

| Field | Type | Notes |
|-------|------|-------|
| `period` | string | the period being looped |
| `iteration` | integer | current iteration count (starts at 1) |
| `max_iterations` | integer | cap (default 3) |
| `no_progress_window` | integer | consecutive-iteration window for the no-progress guard (default 2) |
| `open` | Mismatch-key[] | mismatches still unresolved (no verdict, or `false`/`transient` not yet cleared) |
| `findings` | Mismatch-key[] | `true` verdicts — preserved/reported, never fixed |
| `data_quality` | Mismatch-key[] | `page-error` verdicts |
| `affected_document_ids` | string[] | documents to scope the next `analyze-docs` re-run to (Decision 8) |
| `history` | IterationRecord[] | one entry per completed iteration (see below) |
| `terminate` | object \| null | non-null when the loop must stop |
| `terminate.reason` | enum | `converged` \| `max-iterations` \| `no-progress` |
| `terminate.detail` | string | human-readable explanation |

**IterationRecord**

| Field | Type | Notes |
|-------|------|-------|
| `iteration` | integer | |
| `open_count` | integer | size of `open` at the end of the iteration |
| `open_keys` | string[] | the open mismatch identities (for no-progress comparison) |
| `false_count` | integer | how many were judged `false` (fix candidates) |
| `fixes` | FixProposal-ref[] | PRs opened this iteration |

**Termination logic** (Decision 7 — deterministic):
- `converged`: `open` is empty of `false`/`transient`-unresolved items (only `findings` /
  `data_quality` remain) → stop, report findings (FR-009, US3 scenario 1).
- `max-iterations`: `iteration >= max_iterations` → stop (US3 scenario 3).
- `no-progress`: over the last `no_progress_window` iterations, `open_keys` did not shrink, **or** a
  mismatch id flipped verdict / recurred unresolved → stop (US3 scenario 3; edge case "conflicting
  verdicts").

## Persistence: `data/scrape/<period>.verdicts.json`

A single object per period (full shape in `contracts/verdicts-file.schema.md`):
```jsonc
{
  "period": "2025-12",
  "verdicts": [ /* Verdict records, latest-wins per mismatch_key, history retained */ ],
  "loop_state": { /* LoopState (above), refreshed by `loop-state` */ }
}
```
- Written only by the deterministic CLI (`record-verdict`, `loop-state`) — never hand-edited by an
  agent (mirrors "`apply-extractions` is the only writer of analyses").
- Absent file ⇒ a fresh loop (iteration 1, no verdicts).

## Relationships

```
Mismatch (from `mismatches`) ──identity──> Verdict (review-mismatch) ──verdict=false──> FixProposal (fix-mismatch)
        └────────────────────────── all aggregated by ──────────────────────────────> LoopState (loop-state CLI)
```
