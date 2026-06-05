# Contract: Assessment Report

The PM agent MUST produce each assessment report in this shape. This is the output contract for
FR-002, FR-003, FR-004, FR-005, FR-006, FR-009, FR-013, FR-014.

- **Path**: `docs/assessments/<YYYY-MM-DD>-assessment.md` (append `-2`, `-3`… for same-day reruns)
- **Format**: Markdown, decision-ready prose + tables (FR-012)

## Template

```markdown
# Repository Assessment — <YYYY-MM-DD>

**Run focus**: <full project goal | maintainer-supplied focus>
**Goal reference**: docs/SCOPE-fraud-detection.md
**Repository state**: <git short SHA + branch at time of run>

## 1. Capability Inventory

| Category | Capability | Maturity | Evidence |
|----------|-----------|----------|----------|
| Ingestion/Scraping | <name> | complete\|partial\|stub\|planned | <path> |
| Data Model | … | … | … |
| Auditing Checks | … | … | … |
| Reporting | … | … | … |
| Auth | … | … | … |
| UI/Dashboard | … | … | … |
| Infra | … | … | … |

## 2. Gaps vs Project Goal

| Gap | Severity | Affected Area | Goal Link |
|-----|----------|---------------|-----------|
| <description> | high\|medium\|low | <area> | <e.g. SCOPE Phase 2: CNPJ validation> |

## 3. Source-of-Truth Discrepancies

<!-- FR-009: code vs docs conflicts. State "None found" if none. -->
- <discrepancy or "None found">

## 4. Recommended Next Features (ranked by impact-to-effort)

### 🥇 Top pick: <Title>

- **Gap closed**: <gap>
- **Rationale (goal tie-in)**: <why it advances correctness / forgery detection>
- **Impact**: high\|medium\|low — <one-line justification>
- **Effort**: high\|medium\|low — <one-line justification>
- **Dependencies**: <existing capabilities it builds on>

### Shortlist

| Rank | Feature | Impact | Effort | Gap closed | Dependencies |
|------|---------|--------|--------|-----------|--------------|
| 1 | <top pick> | … | … | … | … |
| 2 | … | … | … | … | … |
| 3 | … | … | … | … | … |

<!-- FR-013: if no high-value gap exists, say so explicitly here instead of padding the list. -->

## 5. Write-Boundary Self-Check

<!-- R7 / SC-005: output of `git status --porcelain`, confirming only docs/assessments/** and
     specs/_handoff/** changed. -->
- Result: <only assessment report (and hand-off, if accepted) changed | LISTED UNEXPECTED CHANGES>
```

## Contract rules

1. All five numbered sections MUST be present every run (section 3 and the FR-013 note may state
   "None found" / "no high-value gap").
2. Exactly one feature is marked the top pick (FR-005).
3. Every shortlisted feature row MUST have non-empty Impact, Effort, Gap, and Dependencies
   (FR-006, SC-003).
4. The report MUST NOT reproduce any secret value (R8); referencing that a secret file exists is
   allowed.
5. The Write-Boundary Self-Check MUST report the actual `git status` outcome (R7).
