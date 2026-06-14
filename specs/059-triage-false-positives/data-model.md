# Phase 1 Data Model: triage-false-positives skill

No persisted entities, no D1 schema, no migration. The "entities" here are the **in-flight data
shapes** the orchestrator reads and aggregates (all transient, held only as terse JSON in the main
context). They are the contract between the `mismatches` CLI, the `fix-document-findings` agent, and
the orchestrator's summary.

## Mismatch row (input — from `mismatches` CLI)

One open finding as printed by `python -m analysis mismatches`. The orchestrator reads only the
identifying fields; it never opens `page_refs`.

| Field            | Type        | Notes                                                              |
| ---------------- | ----------- | ----------------------------------------------------------------- |
| `period`         | string      | `YYYY-MM`.                                                         |
| `kind`           | string      | `amount` / `vendor` / `date` / `page-error` / `document_overpayment`. |
| `attachment_id`  | string?     | Present on per-attachment kinds. Absent on `document_overpayment`. |
| `attachment_ids` | string[]?   | Present on `document_overpayment` (the doc's source attachments).  |
| `entry_id`       | string?     | Present on per-attachment kinds.                                   |
| `entry_ids`      | string[]?   | Present on `document_overpayment`.                                 |
| `document_id`    | string?     | Present ONLY on `document_overpayment`.                            |
| `page_refs`      | object[]    | Materialized image read_paths — **the orchestrator NEVER opens these.** |
| (kind-specific)  | mixed       | e.g. `ledger_amount`/`extracted_amount`, `over_amount`, …         |

## Candidate (derived — the fan-out unit)

A distinct document or attachment carrying ≥1 (filtered) open finding.

| Field          | Type    | Derivation                                                          |
| -------------- | ------- | ------------------------------------------------------------------ |
| `candidate_id` | string  | `row.document_id` if present, else `row.attachment_id`.             |
| `id_kind`      | enum    | `document` (evidence via `document-evidence --id`) or `attachment` (evidence via `mismatches --attachment-id`). |
| `findings`     | int     | Count of mismatch rows mapped to this candidate (for the summary). |

**Uniqueness**: de-duplicated by `candidate_id`. Several findings on one attachment/document collapse
to one candidate (one agent). A per-attachment finding whose `attachment_id` is in a document
candidate's `attachment_ids` **folds into that document candidate** (it is not also dispatched as a
bare attachment — the document-keyed evidence resolver cannot open a bare attachment id, and the
document candidate already covers that attachment's findings). After filtering, an empty candidate set
⇒ dispatch nothing (FR-009).

## Agent result (collected — from `fix-document-findings`)

The terse JSON each fanned-out agent returns; the unit the summary aggregates.

| Field             | Type      | Notes                                                          |
| ----------------- | --------- | ------------------------------------------------------------- |
| `document_id`     | string    | The candidate id passed in (document or attachment).          |
| `attachment_ids`  | string[]  | Resolved source attachments.                                  |
| `corrections`     | object[]  | Each `{mismatch_key, kind, attachment_id, batch_id, from, to, evidence}`. |
| `left_as_finding` | object[]  | Each `{mismatch_key, kind, reason}`; reason ∈ {`true`, `page-error`, `verify-failed`, `unverifiable`, `no-op`}. |
| `escalated`       | object[]  | Each `{mismatch_key, kind, area, hypothesis}`.                 |
| `note`            | string?   | Optional (e.g. "resolved to no attachments").                 |

## Summary (output — the orchestrator's only deliverable to the user)

Aggregated across all agent results. Element-wise sums (SC-004):

| Field         | Type   | Derivation                                                               |
| ------------- | ------ | ----------------------------------------------------------------------- |
| `candidates`  | int    | Number of agents dispatched (= distinct candidates).                     |
| `corrected`   | int    | `Σ len(result.corrections)`.                                            |
| `left`        | object | Counts by reason: `true`, `page-error`, `verify-failed`, `unverifiable`, `no-op`, **`agent-error`** (added by the orchestrator for failed dispatches). |
| `escalated`   | object[] | Flattened `Σ result.escalated`, each listing `{candidate, area, hypothesis}`. |

`agent-error` is the orchestrator-only reason for a candidate whose agent failed/returned
un-parseable output (FR-008); it counts under `left`.
