# Contract: `review-mismatch` agent (US2)

The context-isolated **review worker**. Given one mismatch, it views the evidence and returns a
terse **verdict**. It is the loop's judgment step. It never edits code, schema, the period JSON, or
the verdicts file — recording is the orchestrator's call to the deterministic CLI.

## Definition

- File: `.claude/agents/review-mismatch.md`
- Frontmatter: `name: review-mismatch`, `tools: Read, Glob, Bash`, `model: inherit`, a `color`, and a
  `description` that explains it judges a single mismatch as true/false/transient/page-error and is
  invoked per-mismatch by the orchestrator.

## Input (from the orchestrator)

A single **Mismatch** row (verbatim from `python -m analysis mismatches`), plus its `period`. The
orchestrator passes it as the agent prompt — one mismatch per invocation (invoked in parallel across
mismatches).

## Procedure (in the agent body)

1. **Locate evidence.**
   - Page image(s): open each `read_path` in the mismatch's `page_refs[]` (provided in the summary —
     `{document_id, page_label, read_path}`) with the Read tool. For `duplicate_billing`, `page_refs`
     covers every document in `document_ids`. (No need to read the work manifest — the summary
     carries the refs, per FR-004.)
   - Ledger entry + stored analysis: read the entry and the document's `document_analyses` row from
     `data/scrape/<period>.json` (or via `mismatches`/a read-only helper) — never write it.
2. **Judge** by comparing what is printed on the page against the ledger value(s):
   - **`true`** — the document genuinely disagrees with the books (a real finding). Surfaced, never
     fixed.
   - **`false`** — the system misread or mis-reconciled a legible page. Attach a `root_cause`
     (`area` + `hypothesis`) naming the suspect pipeline part (reading / rollup-precedence /
     grouping / reconciliation-tolerance / other).
   - **`transient`** — the page is legible and the value would likely be correct on a re-read (a
     non-systematic misread), distinct from a code-level flaw.
   - **`page-error`** — the page image is missing/illegible, so no value can be read (not a finding).
3. **Return** ONLY the verdict JSON (see below). No image dumps, no transcripts.

## Output (the agent's entire return value)

```jsonc
{
  "mismatch_key": "2025-12|amount|<doc>|<entry>",   // identity per data-model Decision 4
  "verdict": "false",                                 // true | false | transient | page-error
  "root_cause": {                                      // required iff verdict=false, else null
    "area": "reading",
    "hypothesis": "The DANFE total R$ 1.234,56 is legible; the reader captured the line-item subtotal instead."
  },
  "confidence": "high"                                 // high | medium | low
}
```

## Boundaries (non-negotiable)

- Reads images/JSON only; **never writes** code, schema, the period JSON, `.classify.json`, or the
  verdicts file. The orchestrator persists the verdict via `record-verdict`.
- Judges exactly one mismatch per invocation; returns only the terse verdict (FR-005/SC-002).
- A `page-error` is its own category — never reported as a `true` finding (edge cases).
- Does not re-classify or "fix" anything — that is the orchestrator's / fix worker's job.
