# Phase 1 Data Model: fix-document-findings agent + reclassify CLI

**No new persisted entities, no schema change, no migration.** This feature is an agent prompt plus a
thin CLI wrapper over existing primitives. The "entities" below are the in-flight data shapes the agent
and CLI exchange — all backed by tables that already exist.

## Persisted tables touched (all pre-existing)

| Table | Role here | Written by |
|-------|-----------|------------|
| `page_classifications` | corrected per-page staging (the correction input) | `record_classification` (via `apply-correction` / `reclassify`) |
| `attachment_state` | `classified_at` stamp cleared to re-derive | `_propagate` (`clear_classified_stamp`) |
| `attachment_analyses` (+ `_records`) | re-derived authoritative roll-up | staging-driven `apply_extractions` |
| `documents` / `document_entries` | rebuilt global entity | `build_documents` (inside `run_analysis`) |
| `alerts` | refreshed findings | `run_analysis` |
| `data_corrections` | audit row(s) per changed field | `apply_correction` (TRIAGE-003) |

The mirror tables (`entries`, `attachments`, `accountability_reports`) are NEVER written (read-only for
period/scope resolution).

## In-flight shapes

### Finding (from `document-evidence`)

The agent's evidence unit, one element of `document-evidence`'s `findings[]`:

```jsonc
{
  "period": "2025-12",
  "attachment_id": "<id>",          // present for per-attachment kinds
  "entry_id": "<id>",               // present for per-attachment kinds
  "kind": "amount",                  // amount | vendor | date | page-error | document_overpayment
  "ledger_amount": 320.0,            // kind-specific value fields
  "extracted_amount": 800.0,
  "page_refs": [ {"attachment_id": "<id>", "page_label": "p1", "read_path": ".cache/analysis/2025-12/<entry>_p1.png"} ]
  // document_overpayment carries document_id / attachment_ids / entry_ids / total_value / sum_entries / over_amount instead
}
```

Derived field (computed by the agent, not stored): `mismatch_key` =
`period|kind|attachment_id|entry_id` (per-attachment) or `period|kind|document_id`
(`document_overpayment`) — the `--target-finding` value.

### Corrected pages payload (input to `reclassify` / `apply-correction`)

```jsonc
{ "<page_label>": <fields-object> }   // e.g. {"p1": {"papel_artefato": "nota_fiscal", "valor_total": 320, "numero_documento": "...", "cnpj_emitente": "..."}}
```

Each `<fields-object>` is validated against the frozen `page_classifications` contract by
`validate_page_fields` (typed or flat per feature 055; or an `{"error": ...}` row).

### `reclassify` result (stdout JSON)

```jsonc
{
  "result": "reclassified",          // reclassified | no-op | error
  "attachment_id": "<id>",
  "period": "2025-12",               // resolved from the attachment
  "pages": ["p1", "p2"],             // page labels recorded
  "remote": false
}
```

### Agent result (terse JSON — the agent's ENTIRE return)

```jsonc
{
  "document_id": "<id-or-attachment-id>",
  "attachment_ids": ["<id>", ...],
  "corrections": [                      // findings cleared by an applied data correction
    { "mismatch_key": "...", "kind": "amount", "attachment_id": "...", "batch_id": "...",
      "from": 800.0, "to": 320.0, "evidence": ".cache/.../p1.png" }
  ],
  "left_as_finding": [                  // true / page-error / verify-failed / no-op — untouched, for the human
    { "mismatch_key": "...", "kind": "vendor", "reason": "true" }
  ],
  "escalated": [                        // systematic faults — for the code-fix path, no data change
    { "mismatch_key": "...", "kind": "amount", "area": "rollup-precedence",
      "hypothesis": "first-record-of-role-wins picks the line-item subtotal across this NF class" }
  ],
  "note": "..."                          // optional, e.g. "document resolved to no attachments"
}
```

## State transitions (a single finding through the agent)

```
finding (open)
  ├─ judge: true / page-error      → left_as_finding (no change)
  ├─ judge: systematic-fault       → escalated (no change)
  └─ judge: false-misread
        → apply-correction(mismatch_key, corrected_pages, evidence)
            ├─ applied               → corrections      (finding cleared, data_corrections row, reversible)
            ├─ rolled-back / flagged → left_as_finding  (verify-after failed; data restored)
            ├─ unverifiable          → left_as_finding  (target finding absent before; no change)
            └─ no-op                 → left_as_finding  (corrected == current; no change)
```

## Validation rules

- Corrected pages MUST pass `validate_page_fields` (typed/flat contract) — else reject, write nothing
  (FR-014).
- A correction is allowed only when the page legibly contradicts the recorded value (evidence-bound;
  agent-enforced, FR-007).
- Amount corrections MUST preserve `(numero_documento, cnpj_emitente)` (FR-008) — agent-enforced by
  carrying the existing key fields unchanged into the corrected payload.
- `--remote` defaults off → LOCAL (FR-015).
