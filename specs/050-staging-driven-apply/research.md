# Research: Staging-driven apply-extractions

No NEEDS CLARIFICATION markers from the spec. The decisions below resolve the implementation
approach against the existing code.

## Decision 1: Where to apply the selection filter

**Decision**: Filter at the **group iteration** in `apply_extractions` (`scripts/analysis/extractions.py`),
not in `build_plan`.

**Rationale**: `build_plan` is shared by `plan_extractions` (`docs-plan`) and `apply_extractions`. The
classify/vision phase MUST keep listing all pending groups (its `recorded` flag tells the skill which
pages still need recording). Only `apply`'s selection differs (FR-005). So the filter belongs at the
point `apply_extractions` consumes the envelopes — skip a group when its representative attachment id is
not in the period's staging set.

**Alternatives considered**:
- *Add a parameter to `build_plan` to drop unstaged groups* — rejected: would make the function's output
  depend on whether the caller is plan or apply, coupling two callers and risking the `recorded` flag /
  `docs-plan` output. The spec requires `docs-plan` output unchanged.
- *New `run_selected` column* — rejected by the design doc (§4.1+4.2): costs a migration + every selection
  site + does not itself remove the empty-overwrite risk. Out of scope.

## Decision 2: How to read staging presence

**Decision**: Build a `set[str]` of `attachment_id` values from
`periods[period].raw.get("page_classifications", [])` and check membership of each group's
`representative_attachment_id`.

**Rationale**: The loader already batch-loads the period's `page_classifications` rows into the period
payload (same source as `build_plan`'s `recorded` flag and `D1ExtractionProvider`). Reusing it means
**no extra D1 read** and a pure, trivially unit-testable membership test. Each row carries an
`attachment_id` key.

**Alternatives considered**:
- *A dedicated D1 `SELECT DISTINCT attachment_id FROM page_classifications` per apply run* — rejected:
  redundant round trip; the data is already in memory per period.

## Decision 3: What counts as "has staging"

**Decision**: Presence of **any** staging row for the representative — including an `{"error": ...}`
row — counts as staged. Only the *absence* of all rows skips the group.

**Rationale** (from spec Assumptions / Edge Cases): a recorded error means the page was visited and a
result was deliberately recorded; the existing roll-up already handles a recorded error as a per-page
error without aborting. Treating an error row as "not staged" would wrongly skip a group the operator
chose to (re)classify. The `D1ExtractionProvider` and `build_attachment_analysis` already produce the
correct per-page-error roll-up for such rows, so processing them is byte-identical to today.

## Decision 4: Group-aware, representative-keyed

**Decision**: Key the check on the **representative** attachment id only (`group["representative_attachment_id"]`
/ the `is_representative` member), never a per-member filter.

**Rationale** (FR-003): siblings in a shared-NF group own no staging rows — only the representative's
pages are classified; siblings inherit via fan-out. A naïve per-row filter would drop the siblings of a
genuinely processed group. The representative is the single correct selection key.

## Decision 5: Logging

**Decision**: Keep the existing per-period "Applied N analysis row(s)" log; it naturally reports only
processed rows. Optionally add a debug/info note when a group is skipped for lacking staging (helps the
operator see why an attachment stayed pending), but keep stdout/stderr semantics unchanged (apply does
not print JSON to stdout, so a log line is safe).

**Rationale**: Observability without changing the machine-facing contract. `plan_extractions` is the only
apply-family command that prints JSON to stdout; `apply_extractions` logs to stderr, so a skip log is safe.
