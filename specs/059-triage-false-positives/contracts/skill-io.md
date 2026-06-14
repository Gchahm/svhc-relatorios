# Contract: triage-false-positives skill I/O

The skill is invoked in the main context (it spawns agents). There is no HTTP/CLI surface added; the
"contract" is the skill's input arguments, the commands it is allowed to run, and the summary it
prints.

## Invocation

```
triage-false-positives <YYYY-MM> [--kind <kind…>] [--entry-id <id…>] [--remote]
```

- **`<YYYY-MM>`** (required, first token): the period to triage.
- **`--kind <kind…>`** (optional, repeatable): keep only findings of these kinds
  (`amount` / `vendor` / `date` / `page-error` / `document_overpayment`). Applied as a filter over the
  `mismatches` output. Omitted ⇒ all kinds.
- **`--entry-id <id…>`** (optional): scope to these entries; forwarded to the `mismatches` CLI's
  native `--entry-id`.
- **`--remote`** (optional): operate on production D1/R2. Threaded to BOTH the `mismatches` listing
  and EVERY dispatched agent. Omitted ⇒ local (default). Production is never written implicitly.

## Allowed operations (and ONLY these)

1. **List (read-only)**: `cd scripts && uv run python -m analysis mismatches --periodo <p> [--entry-id …] [--remote]`.
   The orchestrator parses the JSON, applies the `--kind` filter, and derives the candidate set. It
   MUST NOT open any `page_refs` image.
2. **Dispatch (parallel)**: one `Task`/`Agent` call per distinct candidate, `subagent_type:
   fix-document-findings`, prompt = the candidate id, its kind tag (`document`/`attachment`), and the
   target flag. A `document` candidate's agent gathers evidence via `document-evidence --id`; an
   `attachment` candidate's agent gathers evidence via `mismatches --attachment-id`. Sent in a single
   message (parallel fan-out). A per-attachment finding covered by a document candidate is folded into
   it (never dispatched as a bare attachment).
3. **Aggregate + report**: collect each agent's terse JSON, sum into the summary, print it.

**Forbidden**: opening page images; running `classify` / `apply-extractions` / `apply-correction` /
`analyze` / `reclassify` / any data-write command in the orchestrator's own context; merging code;
pushing to `main`; ad-hoc SQL.

## Output (printed summary)

A single concise block, e.g.:

```
Triage of 2099-01 — 2 candidates
  corrected:  1   (amount 296993de… 150→100)
  left:       1   (true 0 · page-error 0 · verify-failed 0 · unverifiable 0 · no-op 0 · agent-error 0 · document_overpayment left as 1 true)
  escalated:  0
```

The exact prose is the orchestrator's; the required content is: candidate count, corrected count,
left-by-reason counts, and escalated list ({candidate, area, hypothesis}). Counts MUST equal the
element-wise sum of the agents' terse results (SC-004).

## Error contract

- A dispatched agent that errors / returns un-parseable output ⇒ its candidate counted as
  `agent-error` under `left`; the batch continues (FR-008/SC-005).
- Zero candidates after filtering ⇒ no agent dispatched; report a zero-candidate "nothing to triage"
  summary (FR-009).
