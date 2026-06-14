# Phase 0 Research: triage-false-positives skill

All "NEEDS CLARIFICATION" items were resolved in the spec's Assumptions/Clarifications (unattended
run). This file records the decisions that shape the orchestrator prompt, grounded in the actual
behavior of the composed assets (verified against the local seeded period `2099-01`).

## Decision 1 — Fan-out unit: the "candidate" (document_id else attachment_id)

**Decision**: Group the `mismatches` rows into distinct **candidates**; a candidate's id is the row's
`document_id` when present (only `document_overpayment` rows carry one), else its `attachment_id`. A
per-attachment finding whose `attachment_id` is one of a document candidate's `attachment_ids` **folds
into that document candidate** (it is not dispatched separately). De-duplicate by candidate id and
dispatch one `fix-document-findings` agent per candidate, tagging it `document` or `attachment` so the
agent picks the right evidence resolver.

**Why the fold-in**: verified that `document-evidence --id <attachment_id>` raises "document not
found" — the resolver is document-keyed only. And a built document's `document-evidence` already
returns every finding on its source attachments (verified: `document-evidence --id 37f12d05…` returns
both the `amount` and `document_overpayment` findings of attachment `296993de…`). So dispatching the
covered attachment separately would both duplicate the work AND hand the agent a bare attachment id
its primary resolver cannot open. Folding it into the document candidate fixes both. A truly unlinked
attachment (no built document) is dispatched as an `attachment` candidate and the agent uses
`mismatches --attachment-id` for its evidence (also verified to work).

**Rationale**: Verified against `python -m analysis mismatches --periodo 2099-01`: per-attachment
kinds (`amount`/`vendor`/`date`/`page-error`) carry `attachment_id` but **no** `document_id`; only
`document_overpayment` carries `document_id` (+ a list of `attachment_ids`). The design (§6 D1) says
"one agent per document", but documents are only built for attachments with a confident
`(numero_documento, cnpj_emitente)`, so attachment-keyed is the universal fallback. The
`fix-document-findings` agent's own contract (#92) accepts "ONE document id (or attachment id)", so
both forms are valid agent inputs — no agent change needed.

**Alternatives considered**:
- *One agent per finding*: rejected — wastes the per-document image-budget isolation and re-reads the
  same page N times; the agent already judges all of a document's findings in one pass.
- *Resolve every attachment to its document first*: rejected — adds a read-only DB hop the
  orchestrator should not own, and attachments with no built document (no confident key) have no
  document to resolve to. Dispatching the attachment id directly is simpler and always works.

## Decision 2 — Read-only listing via `mismatches`, no re-classification

**Decision**: List candidates with `python -m analysis mismatches --periodo <p> [--entry-id …]
[--remote]` (read-only). The orchestrator does NOT run `classify` / `apply-extractions` / `analyze`
to refresh findings first.

**Rationale**: `summarize_mismatches` is a pure read of the persisted `attachment_analyses` match
flags + `document_overpayment` alerts (it only materializes images into the ephemeral cache as a side
effect — which the orchestrator never opens). The findings on the books ARE the work queue; each
fanned-out agent does its own scoped propagation (`apply-correction` → re-derive → analyze) when it
corrects. Re-running the skill later naturally re-reads a shrunk candidate set (self-shrinking queue,
per the issue). This keeps the orchestrator thin and side-effect-free.

**Alternatives considered**: refreshing via the `analyze-docs` agent first — rejected; that is the
classification loop's job (`improve-classification`), would re-open page images at the orchestrator's
altitude, and is out of scope for "triage what is already a finding".

## Decision 3 — Finding filter shape: `--kind` (over output) + `--entry-id` (CLI scope)

**Decision**: `--entry-id <id…>` is forwarded to the `mismatches` CLI's existing `--entry-id` scope.
`--kind <amount|vendor|date|page-error|document_overpayment>` (repeatable) is applied by the
orchestrator as a filter over the `mismatches` JSON `kind` field. No new CLI flag is introduced.

**Rationale**: The `mismatches` CLI already supports `--attachment-id`/`--entry-id` scoping but not a
`--kind` filter; filtering its JSON output by `kind` in the orchestrator is trivial, read-only, and
avoids changing the CLI (Simplicity, FR-005). `--entry-id` is the only scope the CLI natively offers
that maps to a "finding filter" the issue mentions ("all open amount mismatches" → `--kind amount`).

**Alternatives considered**: adding a `--kind` flag to the `mismatches` CLI — rejected; needless CLI
surface for a one-line client-side filter, and would require Python + tests for no extra value.

## Decision 4 — Error isolation: agent failure ≠ batch failure

**Decision**: If a dispatched agent errors, times out, or returns un-parseable output, the
orchestrator counts that candidate under "left for human" with reason `agent-error` and continues
aggregating the rest.

**Rationale**: FR-008/SC-005. A batch over a large period must be resilient; the worst outcome is a
single document going un-triaged (it simply stays a finding for the human — fail-safe for a fraud
tool, where leaving a finding is the safe direction).

## Decision 5 — Skill, not agent; main context; delegation-only

**Decision**: Build `.claude/skills/triage-false-positives/SKILL.md` as a single-file orchestrator
prompt (no `references/` folder), mirroring `improve-classification/SKILL.md`.

**Rationale**: Only the main context can spawn agents (a subagent cannot fan out). The procedure fits
in one file. `improve-classification` is the proven sibling pattern (delegation-only, terse-JSON
read-back, minimal state) — reuse it verbatim rather than inventing a new shape (Simplicity).

## Verified facts (against local seed `2099-01`)

- `mismatches --periodo 2099-01` returns 2 rows (an `amount` on attachment `296993de…` and a
  `document_overpayment` on document `37f12d05…`). Because `296993de…` is a source attachment of
  `37f12d05…`, the amount finding **folds into** the document candidate → **1 distinct candidate**
  (the document), which covers both findings. This is the canonical fan-out used in the quickstart.
  (To exercise a standalone `attachment` candidate, point at an attachment finding whose attachment is
  not backed by a built document.)
- The `fix-document-findings` agent (`.claude/agents/fix-document-findings.md`) returns
  `{document_id, attachment_ids, corrections[], left_as_finding[], escalated[], note?}` — the exact
  shape the summary aggregates.
- `left_as_finding` reasons emitted by the agent: `true`, `page-error`, `verify-failed`,
  `unverifiable`, `no-op` (per the agent's result-map, §4). The orchestrator adds `agent-error` for
  failed dispatches.
