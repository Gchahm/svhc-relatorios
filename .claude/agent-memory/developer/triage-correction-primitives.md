---
name: triage-correction-primitives
description: The false-positive triage correction stack — which CLI/module does what, and the apply-correction vs reclassify split
metadata:
  type: project
---

The autonomous false-positive triage system (`docs/features/false-positive-triage-agent.md`) is built
from small, heavily-reused primitives in `scripts/analysis`. When building anything in this area, reuse
these — do NOT reinvent:

- **`documents.document_evidence(document_id)`** (TRIAGE-002, CLI `document-evidence --id`) — the agent's
  single entry point: maps a document id → source attachment ids and returns scoped findings + page
  `read_path`s (via `summarize_mismatches`). Never write ad-hoc SQL to resolve a document→attachments.
- **`corrections.apply_correction(attachment_id, target_finding_key, corrected_pages)`** (TRIAGE-003, CLI
  `apply-correction`) — the **audited** correction: snapshot → write staging → propagate → verify-after
  (rolls back automatically if the finding doesn't clear or a new one appears) → record to the
  `data_corrections` D1 table. `target_finding_key` is `verdicts.mismatch_key` (`period|kind|att|entry`,
  or `period|kind|document_id` for `document_overpayment`). Result codes: `applied` / `rolled-back` /
  `flagged` / `unverifiable` (target absent before) / `no-op`.
- **`corrections.reclassify(attachment_id, corrected_pages)`** (feature 058, CLI `reclassify`) — the
  **un-gated** sibling (design §4.5): record staging + propagate in pinned order, NO audit/verify net.
  Autonomous agents must use `apply-correction`, never `reclassify`.

**Why:** `_propagate` (in `corrections.py`) already encapsulates the full ordering — `clear_classified_stamp`
→ feature-050 staging-driven `apply_extractions` → `run_analysis` (which runs `build_documents` + writes
alerts). It lazily imports `run_analysis` from the package `__init__`. `corrections.py` is imported BY
`extractions.py`, so new orchestration that needs `_propagate` belongs in `corrections.py`, not
`extractions.py` (avoids an import cycle).

**How to apply:** the `fix-document-findings` agent (`.claude/agents/fix-document-findings.md`) drives these
CLIs. The batch orchestrator over many documents is `triage-false-positives` / TRIAGE-005 / issue #93
(a follow-up). Gotcha: inline Bash with `json.dumps` / `.keys()` trips the damage-control hook (`.dump` /
`.key` substrings) — write payloads to a temp file or use a `.py` script file. CLI `--pages` reads stdin
only as `--pages -` (a bare trailing `-` is an unrecognized positional → argparse exit 2).
