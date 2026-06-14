# Agent Contract: `fix-document-findings`

A context-isolated per-document false-positive correction worker (design §6). Defined at
`.claude/agents/fix-document-findings.md`. Tools: `Bash, Read, Glob`.

## Input (the agent's prompt)

- ONE **document id** (as shown by the UI/alert) — or an **attachment id** — to triage.
- A target: LOCAL by default; the prompt is told to thread `--remote` end-to-end only when explicitly
  asked to operate on production.

## Output (the agent's ENTIRE return — terse JSON, no images/transcripts)

```jsonc
{
  "document_id": "<input id>",
  "attachment_ids": ["<resolved>", ...],
  "corrections":   [ { "mismatch_key", "kind", "attachment_id", "batch_id", "from", "to", "evidence" } ],
  "left_as_finding": [ { "mismatch_key", "kind", "reason" } ],   // reason ∈ true | page-error | verify-failed | no-op | unverifiable
  "escalated":     [ { "mismatch_key", "kind", "area", "hypothesis" } ],
  "note": "..."   // optional
}
```

## Procedure (the prompt encodes this)

1. **EVIDENCE** — run `python -m analysis document-evidence --id <id> [--remote]`. This returns
   `{document_id, attachment_ids, findings[]}` with each finding's `page_refs[]` (materialized image
   `read_path`s). If `attachment_ids` is empty ⇒ return empty buckets + a note. (Never ad-hoc SQL — FR-002.)
2. **JUDGE** — for each finding, open the `page_refs[].read_path` image(s) with the **Read** tool (in the
   agent's OWN context). Crop/upscale mentally for tiny value bands (high-res reads, §4.6). Decide:
   - `true` — the page genuinely disagrees with the books → `left_as_finding` (reason `true`). NEVER touch.
   - `page-error` — image missing/illegible → `left_as_finding` (reason `page-error`). NEVER touch.
   - `systematic-fault` — a recurring code/mapper cause (roll-up precedence, grouping, tolerance) rather
     than an isolated misread → `escalated` with `{area, hypothesis}`. NO data change (§5, FR-006).
   - `false-misread` — a legible page the system misread, isolated → CORRECT (step 3).
3. **CORRECT** (only `false-misread`) — build the corrected per-page `fields` object, **preserving the
   document identity key** `(numero_documento, cnpj_emitente)` for an amount fix (FR-008), changing it only
   when the number/CNPJ itself is the misread. Compute the finding's `mismatch_key`
   (`period|kind|attachment_id|entry_id`, or `period|kind|document_id` for `document_overpayment`). Call:
   ```
   python -m analysis apply-correction --attachment-id <id> --target-finding <mismatch_key> \
       --evidence <page read_path> --pages <json-via-tempfile-or-stdin> [--remote]
   ```
   (Write the JSON payload to a temp file + pipe via stdin to avoid the `.key`/`.dump` Bash-hook substrings
   — §4.6 / FR-007 evidence-bound.)
4. **RESULT-MAP** — read `apply-correction`'s JSON `result`:
   - `applied` → `corrections` (record `mismatch_key`, `batch_id`, `from`/`to`, `evidence`).
   - `rolled-back` / `flagged` → `left_as_finding` (reason `verify-failed`) — verify-after failed; the
     primitive already restored the data.
   - `unverifiable` → `left_as_finding` (reason `unverifiable`).
   - `no-op` → `left_as_finding` (reason `no-op`).
5. **RETURN** — emit ONLY the terse JSON result (FR-010). No page images, transcripts, or full artifacts.

## Guardrails (non-negotiable — design §7)

- **Evidence-bound only** (FR-007): correct ONLY when the page legibly contradicts the record. Never
  "make it match the ledger." When uncertain, LEAVE the finding.
- **Never touch `true` / `page-error`** (FR-005).
- **Preserve identity** for amount fixes (FR-008).
- **Audited path only**: every autonomous data change goes through `apply-correction` (audited +
  verify-after + reversible). The agent does NOT use `reclassify` for autonomous corrections (un-gated).
- **Escalate systematic faults** (FR-006) — do not mass-correct.
- **Thread the target** end-to-end (FR-011); default LOCAL.
- **One document per invocation** — keeps page-image reads within the context budget (FR-012); a batch is
  fanned out by TRIAGE-005 (out of scope).
