# Flow analysis: an agent that removes false-positive findings before human review

> **Status:** analysis / design only — no agent or skill is built yet. This document inventories the
> existing flow, identifies what must change for a per-document "false-positive triage & data-correction"
> agent to work **efficiently and safely**, and proposes the agent/skill shape. It can feed
> `/speckit specify`.
>
> **Companion docs:** the manual flow this automates is recorded in
> [`docs/runbooks/fix-document-vision-mismatch.md`](../runbooks/fix-document-vision-mismatch.md)
> (read it first — it has the data-flow + problem catalogue). Related: the existing **`improve-classification`**
> loop and the [`rollup-amount-false-positives`](./rollup-amount-false-positives.md) analysis.

---

## 1. Goal

Given a **document** (or a batch of open findings), automatically:

1. gather every finding touching it (amount/vendor/date mismatches, page-errors, `document_overpayment`,
   over/under status),
2. look at the actual page image(s) and decide, per finding, whether it is a **real discrepancy** or a
   **false positive** (a legible page the system misread / mis-rolled-up),
3. for a demonstrable misread, **correct the data in place** by re-classifying that attachment (not a code
   change, not a PR), then propagate (`apply-extractions` → `build-documents` → `analyze`) and verify the
   finding cleared,
4. leave real findings and unreadable pages **untouched** for the human.

Net effect: a human opening the dashboard sees a queue scrubbed of vision-noise — only findings that are
genuinely worth a human's attention.

This is exactly the flow performed by hand for document `757dedb0…` (R$ 800 phantom total → corrected to
R$ 320). The runbook is the hand-cranked version; this agent is the automated one.

> **See also §10 — a companion enhancement that strengthens this whole feature:** make the vision step
> produce a **complete, typed transcription** of each document (DANFE / NFS-e / boleto / receipt / payment
> proof schemas) and derive the reconciliation fields with a **deterministic, testable mapper** instead of
> letting the model guess "which number is the total." It is what the UI shows as the "IA extraction," and
> it gives the triage agent far better evidence plus a cheap **re-derive-without-re-vision** correction path.

---

## 2. What the agent must do (the loop, distilled)

```
for each target document/attachment:
  1. EVIDENCE   gather findings + page images (read-only)
  2. JUDGE      per finding: true | false-misread | systematic-fault | page-error
  3. CORRECT    misread → re-classify the attachment (record corrected page extraction)
  4. PROPAGATE  apply-extractions (scoped) → build-documents → analyze (scoped)
  5. VERIFY     re-read findings; confirm the false positive cleared and no NEW finding appeared
  6. AUDIT      record what was changed + why (from→to, evidence) for the human
```

Steps 1 (evidence) and 2 (judge) already exist as the **`review-mismatch`** pattern. The new work is steps
3–6 as a _data_ correction (improve-classification routes step 3 to a _code_ PR instead — see §5).

---

## 3. Existing assets the agent reuses (≈80% is already there)

| Capability                                                                 | Where                                                                                                                               | Reusable as-is?                                                      |
| -------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------- |
| Scoped, read-only finding summary **with page image `read_path`s**         | `summarize_mismatches(..., attachment_ids=, entry_ids=)` → CLI `mismatches --attachment-id/--entry-id`; materializes images from R2 | ✅ yes — this is the evidence feed                                   |
| Per-finding visual judgment (true/false/transient/page-error + root cause) | `review-mismatch` agent                                                                                                             | ✅ yes — judgment pattern                                            |
| Per-page correction primitive                                              | `classify-doc-page` skill + `record-classification --attachment-id --page --json`                                                   | ✅ yes                                                               |
| Re-queue an attachment                                                     | `mark-pending --attachment-id …` (clears `attachment_state.classified_at` **and** its staging rows)                                 | ✅ yes                                                               |
| Roll-up + write analysis (atomic)                                          | `apply-extractions` → `_merge_and_write`                                                                                            | ⚠️ scoping + safety gaps (§4)                                        |
| Rebuild global documents entity                                            | `build-documents` (global, idempotent, prunes stale)                                                                                | ✅ yes                                                               |
| Refresh alerts                                                             | `analyze --periodo` (atomic delete+insert per period)                                                                               | ✅ yes                                                               |
| Verdict / audit bookkeeping                                                | `record-verdict` + `<period>.verdicts.json` (improve-classification)                                                                | ◑ exists but models _code-fix_ verdicts, not data corrections (§4.4) |

**Implication:** the read/evidence half of the agent needs almost nothing new. The gaps are all on the
**write/correction** half and in **scoping/safety**.

---

## 4. Required flow changes (prioritized)

### 4.1 + 4.2 🔴 BLOCKING — make `apply` **staging-driven** (no schema change) — DECIDED

**The hazard (verified in code).** `apply-extractions --periodo` walks **every** pending+paged attachment in
the plan. For each it calls `build_attachment_analysis(..., provider)`; when the staging provider returns
nothing for all pages, the result is `error="no page produced a parseable response"` with **zero records**,
and `_merge_and_write` **still writes it** — deleting the prior analysis + records and stamping
`classified_at`. So any pending attachment whose staging rows were already pruned (feature 035 prunes them
after a successful apply) gets its **good analysis overwritten with an empty one**.

**Root cause.** The two pipeline phases have _different_ correct selection criteria, but `apply` borrows the
wrong one:

| phase                                 | "what to select" should be                                        | uses today                  |
| ------------------------------------- | ----------------------------------------------------------------- | --------------------------- |
| `docs-plan` (what to **show vision**) | **pending** = `classified_at IS NULL` (+ `mark-pending` re-queue) | ✅ correct                  |
| `apply` (what to **roll up**)         | **what was actually classified** = has staging rows               | ❌ borrows the pending plan |

**Change (single, minimal, no migration).** Make `apply` process **only the groups whose representative has
staging rows** in `page_classifications`. This one change is both the safety guard _and_ the scoping
mechanism:

- _Safety:_ an attachment with no staging (a pruned bystander, or one whose vision step crashed before
  recording) is simply **not visited** — it stays pending and self-heals on a later real classification.
  Nothing is overwritten with an empty roll-up.
- _Scoping:_ you select an attachment for `apply` **by recording its staging** (`record-classification`).
  A targeted correction touches only what you recorded — no global pending mutation, no id flags.
- _Group-aware:_ key the check off the **group representative** (siblings carry no staging and inherit the
  rep's extraction via fan-out), not a naïve per-row staging filter.

This is why it **eliminates the manual isolation step entirely**: in the manual fix the 12-page bystander
had to have its stamp restored _only because_ `apply` walked the pending plan. Staging-driven `apply` never
visits it. The problem stops existing rather than needing a workaround.

`docs-plan`, the loader pending query, `mark-pending`, `classify-period`, and `improve-classification` keep
using `classified_at IS NULL` for the **vision** phase — unchanged. Only `apply`'s group selection changes
(localized to `apply_extractions` in `scripts/analysis/extractions.py`).

> **Rejected alternative — an explicit `run_selected` column (the earlier idea in this thread).** It would
> split `classified_at` (status) from a new selection flag and is well-aligned with feature 016, but it costs
> a migration + refactoring every selection site + keeping two columns atomically coherent + a "who enqueues
> new scrapes" decision — and it does **not** remove the empty-overwrite risk on its own (a flagged row with
> no staging still clobbers, so you'd need this guard anyway). Its only unique benefit would be a _durable
> queryable run-queue_, but the batch orchestrator's real queue is the **open-findings set**, already durable
> and re-derivable on demand from `mismatches` (and self-shrinking as corrections land). "What will apply
> touch?" stays inspectable here too: `SELECT DISTINCT attachment_id FROM page_classifications`. So the column
> buys complexity without a benefit that matters here. **Not adopted.**

> Hazard captured as project memory `pending-without-staging-destructive` and runbook Problem #2.

### 4.3 🟠 HIGH — a **document → attachment(s)** resolver

The agent is handed a _document_ id (that's what the UI/alert shows), but correction happens at the
_attachment_ level. A document is global and N:N with entries (`document_entries.source_attachment_id`).
There is no CLI that maps a document id to its source attachment ids today (the manual flow used raw SQL).

**Change (small).** Either add `mismatches --document-id <id>` (expands to the doc's `attachment_ids` and
emits the same scoped summary + `page_refs`), or a tiny `document-evidence --id <id>` command returning
`{document, entries, attachments[], analyses[], page_refs[]}` in one shot. This is the agent's single
entry point and avoids ad-hoc SQL in the agent. (With 4.2, enqueueing the resolved attachments is the same
`run_selected` UPDATE.)

### 4.3 🟠 HIGH — a **document → attachment(s)** resolver

The agent is handed a _document_ id (that's what the UI/alert shows), but correction happens at the
_attachment_ level. A document is global and N:N with entries (`document_entries.source_attachment_id`).
There is no CLI that maps a document id to its source attachment ids today (the manual flow used raw SQL).

**Change (small).** Either add `mismatches --document-id <id>` (expands to the doc's `attachment_ids` and
emits the same scoped summary + `page_refs`), or a tiny `document-evidence --id <id>` command returning
`{document, entries, attachments[], analyses[], page_refs[]}` in one shot. This is the agent's single
entry point and avoids ad-hoc SQL in the agent.

### 4.4 🟡 MEDIUM — a **data-correction verdict + audit trail** (distinct from the code-fix `false`)

The existing verdict taxonomy (`review-mismatch`) is built for the _code-fix_ loop: a `false` verdict →
`fix-mismatch` opens a **PR**. The new agent's correction is a **data re-classification**, not code. We need
a first-class record of "this finding was auto-resolved as a false positive by re-classifying attachment X:
`valor_total` 800→320, because page p1 reads 320 (PIX proof + ledger agree)". A human must be able to audit
and reverse it.

**Change.** Extend the verdict/audit store (reuse `<period>.verdicts.json` with a new
`resolution: "data-correction"` shape, or a dedicated `corrections` log, or an `alerts.notes` graft) to
capture per-correction: `{attachment_id, page, field, from, to, evidence, agent, timestamp}`. The
correction must be **traceable and reversible**, not silent. (Open question Q3.)

### 4.5 🟡 MEDIUM — a single composite "reclassify-attachment" step (ergonomics)

The correction is a 4–5 command sequence (`mark-pending` → `record-classification` per page →
`apply-extractions` → `build-documents` → `analyze`). A composite command (e.g.
`reclassify --attachment-id X --pages <json>`) shrinks the agent's orchestration surface and pins the order.
With staging-driven `apply` (4.1+4.2), a mid-sequence crash is already **non-destructive** (an attachment
left pending with no staging is simply skipped by `apply`), so this is purely ergonomic, not a safety
requirement.

### 4.6 🟢 LOW — guardrails & ergonomics (mostly agent-prompt, some flow)

- **Identity-key preservation (correctness).** The document key is `(numero_documento, cnpj_emitente)`.
  To fix an _amount_ misread, the agent MUST keep those stable so `total_value` is corrected **in place**;
  changing them re-keys the document (prunes the old, spawns a new). Only change them when the _number/CNPJ
  itself_ is the misread. (Runbook Problem #4.)
- **Image budget → fan-out.** A context exhausts ~18 page images (memory `analyze-docs-batch-size`). A batch
  orchestrator must fan out **one sub-agent per document** (like improve-classification fans out
  `review-mismatch`), not view all pages in one context.
- **`--remote` threading.** Every step has `--remote`; the agent must thread it end-to-end or it silently
  fixes only local data (runbook Problem #7).
- **Bash hook substrings.** The damage-control hook blocks `.key` / `.dump` substrings; the agent should
  avoid `json.dumps`/`.keys()` in inline Bash or write to a temp file + `jq` (runbook Problem #6).
- **High-res reads.** Value bands are tiny; the agent should crop+upscale before asserting a number
  (runbook Problem #5).

---

## 5. Relationship to `improve-classification` (don't reinvent or collide)

`improve-classification` is **period-scoped** and treats a `false` mismatch as a **systematic code fault** →
delegates `fix-mismatch` → opens a **human-gated PR** → re-queues → re-runs. Its "fix" changes _code_.

The new agent is **document/attachment-scoped** and its "fix" changes _data_ (re-classification), with **no
PR**. The two are complementary, and the boundary between them is the single most important judgment the new
agent makes:

```
finding →
  true / page-error                         → LEAVE for human (never touch)
  misread of a legible page, ISOLATED       → DATA-CORRECT here (re-classify the attachment)
  fault that recurs across many findings     → ESCALATE to improve-classification / fix-mismatch (code PR)
    (rollup-precedence / grouping / tolerance)
```

**Anti-pattern to avoid:** hand-correcting 100 documents one-by-one when the real cause is one systematic
code bug. The agent must detect "same root cause across N findings" and escalate to a code fix rather than
mass-papering data. (See `rollup-amount-false-positives.md` for exactly such a systematic class — those are
_not_ per-document data corrections.)

The new agent can be seen as a **lightweight, data-only sibling** of `improve-classification`:

- shares: `review-mismatch`-style evidence+judgment, `mark-pending`/`apply`/`build-documents`/`analyze`.
- differs: per-document scope, data-correction instead of PR, no `loop-state`/iteration/PR machinery.

---

## 6. Proposed shape (for the follow-up build — not built here)

- **`fix-document-findings` agent** (context-isolated, like `review-mismatch` + a correction step):
  input = one document id (or attachment id) + `--remote`. It runs evidence → judge → correct → propagate →
  verify for that ONE document and returns a terse JSON result
  (`{document_id, corrections:[…], left_as_finding:[…], escalated:[…]}`). It views page images in its OWN
  context (image budget) and returns no images. Tools: `Bash, Read, Glob`.
- **`triage-false-positives` skill** (thin orchestrator, like `improve-classification`): input = a period or
  a filter ("all open amount mismatches"). It lists candidate documents (read-only, via `mismatches`), fans
  out **one `fix-document-findings` agent per document** (parallel, budget-isolated), collects terse
  results, and reports a summary: corrected N, left M findings, escalated K systematic faults. Coordination
  only — holds no images.

Both are unblocked once §4.1 (safety) + §4.2/4.3 (scoping/resolver) land; §4.4/4.5 make them clean.

---

## 7. Guardrails (the correctness floor — non-negotiable)

This is a **fraud/forgery audit tool**: hiding a real finding is far worse than leaving a false positive.

1. **Evidence-bound only.** A correction is allowed _only_ when the page legibly shows a value that
   contradicts what the system recorded (page=320, recorded=800, and independent signals agree). No
   heuristic "make it match the ledger" — that would erase genuine discrepancies (cf. memory
   `vendor-cnpj-matching-unsafe`, and the false-negative caution in `rollup-amount-false-positives.md`).
2. **Never touch `true` or `page-error`.** Real disagreement and illegible pages go to the human, full stop.
3. **Correct in place, preserve identity.** Keep `(numero_documento, cnpj_emitente)` stable for amount fixes.
4. **Auditable & reversible.** Every correction logs from→to + evidence (§4.4); a human can review/undo.
5. **Escalate systematic faults**, don't mass-correct (§5).
6. **Verify after.** Re-read findings post-correction; confirm the target cleared and **no new finding
   appeared** (a correction that trades one mismatch for another is wrong).

---

## 8. Decisions (confirmed)

- **D1 — Trigger granularity: BOTH.** Build the context-isolated per-document `fix-document-findings` agent
  **and** the `triage-false-positives` skill that fans it out across a period / a filter. (§6 stands as-is.)
- **D2 — Correction method: agent records the verified value.** The agent reads the page image at high
  resolution, establishes ground truth, and records the corrected extraction via `record-classification`
  (deterministic — what the manual fix did). It does **not** rely on a blind vision re-run that could repeat
  the misread. The cited page image is the evidence attached to the correction.
- **D3 — Autonomy: FULLY AUTONOMOUS.** Corrections apply directly, with **no** human pre-approval gate.
  → **Consequence:** the audit trail + reversibility (§4.4) and the post-correction verification (§7.6) are
  now **load-bearing, not optional** — they are the only safety net once a correction lands unreviewed.
  Treat §4.4 as 🔴 (promoted from 🟡): a correction MUST record `{attachment_id, page, field, from, to,
evidence_read_path, agent, timestamp}` to a durable, human-visible, reversible store before/with the write,
  and the agent MUST re-verify (target cleared + no new finding) and roll back / flag if verification fails.

- **Q3 (audit store) — still open:** reuse `<period>.verdicts.json` (new `resolution:"data-correction"`
  shape) vs a dedicated corrections log vs `alerts.notes`. Decide during `/speckit specify`.
- **Q5 (local vs remote) — still open:** default target for autonomous corrections. Lean toward an explicit
  `--remote` per run (never an implicit prod write).

---

## 9. Summary of concrete changes

| #       | Change                                                                                                                                                 | Priority                        | Type                 |
| ------- | ------------------------------------------------------------------------------------------------------------------------------------------------------ | ------------------------------- | -------------------- |
| 4.1+4.2 | make `apply` **staging-driven** (process only groups whose rep has staging rows) — fixes safety **and** scoping in one change, **no schema/migration** | 🔴 blocking                     | safety+scoping, code |
| 4.3     | document→attachment resolver (`mismatches --document-id` or `document-evidence`)                                                                       | 🟠 high                         | ergonomics, code     |
| 4.4     | data-correction verdict + audit trail + reversibility                                                                                                  | 🔴 blocking (full autonomy, D3) | auditability         |
| 4.5     | composite `reclassify --attachment-id` (safe ordering)                                                                                                 | 🟡 medium                       | ergonomics           |
| 4.6     | guardrail/ergonomic notes (identity key, fan-out, remote, hooks, high-res)                                                                             | 🟢 low                          | agent prompt         |
| 6       | `fix-document-findings` agent + `triage-false-positives` skill                                                                                         | —                               | new agents/skill     |
| 10      | **typed full-document transcription + deterministic interpretation** (see §10)                                                                         | 🟠 high — companion             | extraction refactor  |
| 11      | extract the **vision transcriber as a standalone, reusable module** (Claude API + structured output; own dep) — see §11                                | 🟠 high — companion             | architecture         |

The read/evidence path needs **no** change. The whole feature hinges on the **§4.1+4.2 staging-driven
`apply`** (one localized code change, no schema/migration — fixes both safety and scoping) plus the
**§4.3 resolver** and the **§4.4 audit trail** (load-bearing under full autonomy); everything else is polish
and guardrails. **§10** is a larger companion refactor that multiplies the value of all of the above.

---

## 10. Companion enhancement: typed full-document transcription + deterministic interpretation

> Requested as an improvement to the extraction flow. Larger than §4–§7 and valuable on its own, but it
> _strengthens_ the triage agent (better evidence + a cheap correction path), so it lives here. May warrant
> its own `/speckit specify`.

### 10.1 The problem with today's extraction

The vision step (`classify-doc-page`) is asked to both **read** the page _and_ **interpret** it — to decide
"which number is the total," "which party is the issuer." It outputs a flat ~10-field object
(`valor_total`, `cnpj_emitente`, …). Two failure modes follow directly:

- **Interpretation errors become data errors.** The 757dedb0 bug (`valor_total` 800 vs the page's 320) was
  the model picking the wrong number; the NFS-e _did_ legibly show 320, the model just interpreted wrong.
- **Almost everything on the page is thrown away.** Real example — the DANFE on
  `dashboard/documents/8293d3db…` (`000006227`, AGUA MARINHA PISCINAS):

    | the page contains                                                | the flat extraction captured                          |
    | ---------------------------------------------------------------- | ----------------------------------------------------- |
    | 44-digit chave de acesso, série, natureza da operação, protocolo | —                                                     |
    | emitente block (name, **CNPJ**, IE, address)                     | name **misread** ("AGUA **MORENA**"), **CNPJ = null** |
    | destinatário (SÃO VICENTE HOME CLUB, CNPJ, address)              | —                                                     |
    | item table (código, descrição, NCM, CFOP, qty, unit price, ICMS) | —                                                     |
    | totais (base ICMS, valor ICMS, vProd, **vNF = 2790,00**)         | `valor_total: 2790` only                              |
    | fatura / duplicatas (installments)                               | —                                                     |

    So the "IA extraction" the UI shows (feature 048) is thin and even _wrong_ on the issuer — the reviewer
    can't see what the AI saw, which was the original complaint.

### 10.2 The change: transcribe into a typed schema, then derive deterministically

Split the one fuzzy step into two:

```
PAGE IMAGE ──vision (fuzzy)──▶  TYPED TRANSCRIPTION            ──deterministic mapper (pure)──▶  reconciliation fields
                                (full, schema-per-doc-type)        (per type, testable)              (valor_total, cnpj, …)
                                = what the UI shows                = feeds nf_total_for_reconciliation / roll-up
```

1. **Vision transcribes everything into a typed JSON keyed by document type.** The model first detects the
   type (it already emits `papel_artefato` / `tipo_documento`), then fills that type's schema with _every_
   field present on the page — it no longer decides what "the total" is, only records labeled values
   verbatim (e.g. NFS-e: `valores.valor_servico=320`, `valores.valor_liquido=320`, `retencoes.irrf=0`).
2. **A deterministic, pure mapper per type derives the reconciliation fields** the pipeline needs
   (`valor_total`, `valor_liquido`, `valor_pago`, `cnpj_emitente`, `numero_documento`, …) by typed field
   access — e.g. `danfe → valor_total = totais.valor_total_nota`; `nfse → valor_total = valores.valor_liquido`;
   `comprovante → valor_pago = valor`; `boleto → valor_total = valor_documento`. This **replaces the model's
   guesswork** (and the "first-record-of-role-wins" selection in `_rollup_attachment_fields` —
   see [`rollup-amount-false-positives.md`](./rollup-amount-false-positives.md), which this principled-fixes)
   with versioned, unit-testable rules.

The 757dedb0 bug could not have happened under this model: the model would transcribe `valor_servico=320 /
valor_liquido=320`, and the `nfse` mapper would deterministically pick 320.

### 10.3 Schema-per-type registry

A small registry maps a detected type → `{ json schema (for the vision prompt + validation), deterministic
mapper, UI renderer }`. Initial types from what the corpus actually contains:

- `danfe` (NF-e) · `nfse` (DANFSe) · `recibo` · `boleto` · `comprovante_pagamento` (PIX/TED/boleto) ·
  `outro` (generic fallback: full free-text + best-effort key/values, never blocks).

Each typed schema mirrors the real Brazilian layout (NF-e/DANFSe are national standards, so the schemas are
well-defined, not invented). Adding a new document type = add a schema + mapper + renderer; nothing else
changes.

### 10.4 Storage, validation, UI — mostly additive

- **Storage:** the rich JSON lives in the existing `attachment_analysis_records.response` (TEXT) — **no DB
  migration for storage**, just larger payloads. The derived fields keep populating the existing
  `attachment_analyses` roll-up columns (now via the mapper, not the model). Add a `schema_version` (or rely
  on a `doc_type` discriminator inside the JSON) so old flat rows and new typed rows coexist; the mapper +
  UI handle both until re-classification catches up.
- **Validation:** `record-classification` stays the contract gate — validate the payload against the type's
  schema (required keys + types). Lightweight stdlib validation (no new dep) keeps the analysis package
  stdlib-only; the full JSON Schemas double as the vision prompt spec.
- **UI:** the `AttachmentAnalysisDetailDialog` becomes **type-aware** — a DANFE renderer (header / parties /
  item table / totais), an NFS-e renderer, etc., with a generic JSON-tree fallback, and the
  reconciliation fields highlighted with provenance ("`total_value` ← `totais.valor_total_nota`"). This is
  the "show the whole text as the IA extraction" the request asks for, and it directly extends feature 048.

### 10.5 Why this multiplies the triage agent's value

- **Better evidence.** The agent (and the human) judge against a _complete_ typed transcription, not 5 flat
  fields — far fewer ambiguous calls.
- **A new, cheap correction class — re-derive without re-vision.** If a finding is caused by the _mapper_
  picking the wrong field (not a transcription error), fix the mapper once and **re-derive the reconciliation
  fields from the stored transcriptions** — no image reads, no vision cost, and it corrects _every_ document
  of that type at once. This is strictly better than per-document re-classification for systematic cases, and
  refines the §5 decision tree into three branches:

    ```
    real disagreement on the page          → leave for human (true finding)
    transcription itself is wrong (misread) → re-classify that one attachment (vision)   [§4 path]
    transcription right, mapper wrong        → fix the deterministic mapper + RE-DERIVE   [new, cheap, systematic]
    ```

- **More precise corrections.** The agent's "record the verified value" (D2) becomes "correct the typed
  field" (e.g. set `emitente.nome = "AGUA MARINHA"`, add the missing `emitente.cnpj`); the mapper re-derives
  the rest. A new `re-derive` step (run the mappers over stored transcriptions → roll-ups → `build-documents`
  → `analyze`) is the propagation path, parallel to `apply-extractions` but image-free.

### 10.6 Costs / risks

- **More vision tokens + more transcription surface** per page. Mitigated: the fields that matter are
  validated and consumed deterministically; a transcription slip in an irrelevant field doesn't move a
  reconciliation value.
- **Schema/mapper/renderer maintenance** — a registry to keep current as new document shapes appear. The
  `outro` fallback ensures unknown types never block the pipeline.
- **Type-detection errors** route to the wrong schema/mapper. Needs a confident-type gate + the ability to
  _correct the type_ (the triage agent can), and the generic fallback.
- **Coexistence** of old flat records and new typed records during rollout (handled by `schema_version` +
  dual-path mapper/UI, or a re-classification campaign for high-value periods).

### 10.7 Open decisions

- **T1 — Schema format:** JSON Schema docs (for the prompt) + lightweight stdlib validation, vs a heavier
  validator dependency. Lean: JSON Schema as spec, stdlib validation in `record-classification`.
- **T2 — Rollout:** re-classify everything into typed schemas (cost), or only new scrapes + on-demand when
  the triage agent touches a document (gradual). Lean: gradual, with the dual-path mapper/UI.
- **T3 — Sequencing vs the triage agent:** land §10 first (so the agent gets rich evidence + re-derive), or
  ship the §4 triage primitive first and layer §10 after. Both orders work; §10 is the bigger build.

---

## 11. The vision transcriber as a standalone, reusable module

> The §10 transcription engine is the most portable piece of this whole system — "image of a Brazilian fiscal
> document → typed JSON" has nothing project-specific in it. Build it as a self-contained module with a clean
> interface and its own dependency, so it can be lifted into other projects (or its own repo) later.

### 11.1 Why separate it

- **Reuse.** Any project handling NF-e / NFS-e / boletos / receipts wants the same "page image → typed JSON"
  capability. The schemas (§10.3) are national-standard layouts, not SVHC-specific.
- **It protects the stdlib-only invariant.** The `analysis` package is deliberately **stdlib-only**
  (CLAUDE.md). A transcriber that calls the Claude API needs the `anthropic` SDK + image handling — putting
  it in its **own** module keeps that dependency out of `analysis`, which keeps consuming pure typed JSON.
- **It removes the orchestrator's image budget.** Today the _orchestrating agent itself_ reads page images
  in-context (the ~18-image cumulative budget — memory `analyze-docs-batch-size`). If transcription is a
  script that calls the API per page, the orchestrator never loads an image into its own context — it shells
  out and gets JSON back. That budget constraint, and the per-context fan-out gymnastics, largely disappear.

### 11.2 The boundary (a clean, stable interface)

A pure transcription seam, no knowledge of D1 / attachments / periods / reconciliation:

```
transcribe(image_bytes | path, doc_type?: "danfe"|"nfse"|"boleto"|"recibo"|"comprovante"|"auto")
    → { doc_type, schema_version, fields: <typed JSON per §10.3>, parse_errors? }
```

Exposed as both a **library function** and a **CLI** (`transcribe --image <path> [--type auto] → JSON on
stdout`). The project's `record-classification` becomes a **thin adapter**: call the transcriber → validate
→ write the staging row. The deterministic mappers (§10.2) consume the typed JSON downstream. Nothing in the
transcriber imports `analysis`; the only contract between them is the typed-JSON schema.

### 11.3 How the vision happens — a pluggable backend (CLI **or** API)

The model call sits behind a **swappable backend** chosen by a prop (`backend: "cli" | "api"`), because the
two have different sweet spots and the rest of the module doesn't care which ran. **Schema validation lives
_above_ the backend** — whichever backend returns the JSON, the module validates it against the §10 type
schema itself — so the backends are freely interchangeable and the typed-JSON guarantee never depends on the
backend.

Two backends:

- **`cli` — shell out to `claude -p` (Claude Code, headless).** Reuses the existing **Claude Code login — no
  `ANTHROPIC_API_KEY`, no `anthropic` SDK dependency.** The subprocess reads the image and returns JSON (we
  parse + validate it our side; the CLI doesn't _enforce_ a schema). Because it runs in its **own subprocess
  context**, it still keeps page images out of the orchestrator's budget (§11.1). Best for **per-document,
  on-demand** transcription — the triage agent's corrections.
- **`api` — Anthropic Messages API via the `anthropic` SDK** (per the bundled `claude-api` skill — consult it
  when implementing). A request with an `image` block + `output_config: {format: {type: "json_schema",
schema}}` (via `messages.parse()`), so the typed shape is **enforced** at the wire, then validated again.
  Needs an `ANTHROPIC_API_KEY` + the SDK. Unlocks **Batch (50%) + prompt caching** (§11.5). Best for
  **bulk / production** transcription.

_Schema constraints to respect on the `api` backend:_ structured outputs allow objects/arrays/enums/`anyOf`/
`$ref` and require `additionalProperties:false`, but **not** numeric/length bounds or recursion — the SDK
strips unsupported keywords and validates them client-side, so keep the typed schemas within that subset
(resolves T1: JSON Schema is both the prompt spec and the wire contract). The `cli` backend has no wire
enforcement at all, which is exactly why the module's own validation layer is mandatory.

**Default `backend: "cli"`** — it matches this repo's current auth posture (no new secret, reuses Claude
Code), and per-document corrections are the primary use case. Switch to `api` for the bulk backfill campaign.

**Model tier (decision T4 below):** on the `api` backend, single-call extraction is the right surface —
`claude-opus-4-8` (most capable; high-res vision helps dense DANFEs), `claude-sonnet-4-6` (accuracy/cost
balance), `claude-haiku-4-5` (cheapest bulk, backstopped by the deterministic validation). The `cli` backend
uses whatever model the Claude Code session is configured with.

This **replaces** today's in-context vision (the orchestrating Claude Code agent reading the image with its
`Read` tool — portable only inside Claude Code, and charges the orchestrator's image budget). `classify-doc-page`
either wraps this module or is retired in its favor; the orchestrator stops doing vision itself.

### 11.4 What's reusable vs project-specific

| Reusable (the module / future package)                    | Project-specific (stays in this repo)                                                                                                                                                                                   |
| --------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `transcribe()` + CLI; the Claude API call; image handling | `record-classification` adapter; D1 staging write                                                                                                                                                                       |
| The typed per-type **schemas** (§10.3)                    | The **deterministic mappers** (§10.2) — _mostly_ reusable (NF-e total = vNF is universal), but "which field SVHC reconciles on" is arguably app policy; start them app-side, extract later if a second consumer appears |
| Prompt + model config per type                            | Roll-up into `attachment_analyses`, `build-documents`, alerts                                                                                                                                                           |

### 11.5 High-volume transcription (bulk re-classification campaigns)

The §10.7-T2 "re-transcribe a period/backlog into typed schemas" campaign is **not latency-sensitive**, and
these are the concrete reason to reach for the **`api` backend** here (they have no `cli`-backend equivalent),
per `claude-api`:

- **Batch API** (`/v1/messages/batches`) — submit a whole period's pages as one batch at **50% cost**, async
  (most finish ≪ 24h), up to 100K requests/256MB. Structured outputs work in batches. Ideal for the gradual
  rollout. (Caveat: the server-side refusal-`fallbacks` param isn't available on Batches — not relevant to
  fiscal transcription, but note it.)
- **Prompt caching** — the per-type **instruction + JSON schema is a stable prefix**; the page image is the
  volatile suffix. Cache the prefix so a run over many pages of the same type pays the instruction/schema
  cost once (mind the min cacheable prefix: 4096 tokens on Opus 4.8 / Haiku 4.5, 2048 on Sonnet 4.6).
  Structured-output schemas also get a 24h server-side compile cache after first use.

These two together make a full-corpus typed re-transcription affordable, which is what unlocks the §10.5
"re-derive from stored transcriptions" power for historical data.

### 11.6 Placement & dependencies

- A self-contained module — e.g. `tools/doc-transcribe/` (or a top-level package), **zero imports** from
  `scripts/analysis`. Extractable to its own repo with no untangling.
- Dependencies are **per-backend**: the `cli` backend needs only the `claude` binary on PATH (no Python
  dep); the `api` backend pulls in the `anthropic` SDK as an **optional extra** (e.g. `pip install
doc-transcribe[api]`). Either way the dependency stays out of the stdlib-only `analysis` pipeline.
- Auth is **per-backend** too: `cli` uses the existing Claude Code login (nothing new); `api` reads
  `ANTHROPIC_API_KEY` from the environment (never committed) — same posture as every other secret here.

### 11.7 Open decisions

- **T4 — Model tier for transcription:** `claude-opus-4-8` (default, best fidelity) vs `claude-sonnet-4-6`
  (balance) vs `claude-haiku-4-5` (cheapest bulk). Likely **tiered**: Sonnet/Opus for first-pass accuracy,
  Haiku for bulk re-runs validated by the deterministic mappers. Decide during `/speckit specify`.
- **T5 — Backend default & rollout (DECIDED-ish):** pluggable `backend: "cli" | "api"` behind one interface,
  schema validation above both. Default **`cli`** (reuses Claude Code auth, no new secret — fits per-document
  triage corrections); use **`api`** for the bulk backfill campaign (Batch + caching). The `api` backend's
  SDK + `ANTHROPIC_API_KEY` are an **optional** dependency, pulled in only when that backend is selected — so
  a CLI-only deployment needs neither. Confirm during `/speckit specify`.
- **T6 — Mappers' home:** ship the deterministic mappers inside the reusable package (maximally portable) or
  keep them app-side (SVHC reconciliation policy). Lean: app-side until a second consumer needs them.
