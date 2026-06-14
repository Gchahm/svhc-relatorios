# Quickstart: triage-false-positives skill

## Prerequisites

- Local Miniflare D1/R2 seeded with the synthetic period (`pnpm e2e:seed`) — it carries period
  `2099-01` with two open findings: one `amount` mismatch (attachment `296993de…`, ledger 100 vs
  extracted 150) and one `document_overpayment` (document `37f12d05…`).
- The `fix-document-findings` agent exists (merged via #92) and the `mismatches` CLI runs.

## Verify the read-only listing (what the orchestrator sees)

```bash
cd scripts && uv run python -m analysis mismatches --periodo 2099-01
```

Expect 2 rows, which collapse to **1 distinct candidate**:
- `kind=amount` on attachment `296993de…` and `kind=document_overpayment` on document `37f12d05…`.
- Because `296993de…` is a source attachment of document `37f12d05…`, the amount finding **folds into**
  the document candidate → 1 candidate = document `37f12d05-4cb3-5fd9-8f80-761c8072832b` (its agent
  triages both findings).

## Run the skill (in the Claude Code main context)

```
triage-false-positives 2099-01
```

Expected behavior:
1. The skill runs `mismatches --periodo 2099-01` (read-only), folds the amount finding into the
   document candidate, derives **1 candidate** (document `37f12d05…`).
2. It dispatches **exactly 1** `fix-document-findings` agent (the document candidate), local target
   (no `--remote`).
3. It collects the agent's terse JSON and prints one summary: candidate count (1), corrected count,
   left-by-reason counts, escalated list.
4. The orchestrator's own transcript shows **no page-image Read** — all image work is inside the
   agents.

## Filtered run

```
triage-false-positives 2099-01 --kind document_overpayment
```

Expect only the `document_overpayment` finding kept → still the 1 document candidate `37f12d05…`. With
`--kind amount`, the amount row survives the kind filter but its attachment is not covered by any
SURVIVING document candidate (the overpayment row was filtered out), so it is dispatched as an
`attachment` candidate (`296993de…`) → 1 agent using `mismatches --attachment-id` for evidence.

## Empty run

```
triage-false-positives 2099-12
```

A period with no findings → 0 candidates, no agent dispatched, "nothing to triage" summary, no error.

## Acceptance mapping

- SC-001 — a corrected false positive disappears from a fresh `mismatches`; a `true` finding remains.
- SC-002 — orchestrator transcript opens zero page images.
- SC-003 — N distinct candidates ⇒ N agents dispatched in parallel.
- SC-004 — printed counts equal the sum of the agents' terse results.
- SC-005 — a failing agent is reported `agent-error`; the batch still completes.
