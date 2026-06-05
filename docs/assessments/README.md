# Repository Assessments

This folder holds **dated assessment reports** produced by the PM agent
(`.claude/agents/pm.md`). Each report is a point-in-time snapshot of the project's capabilities,
the gaps between them and the project goal (verifying scraped fiscal data/docs and detecting
forgery/corruption — see `docs/SCOPE-fraud-detection.md`), and a ranked recommendation for the
next feature to build.

## Naming convention

```
docs/assessments/<YYYY-MM-DD>-assessment.md
```

If more than one assessment is run on the same day, append a numeric suffix:
`<YYYY-MM-DD>-assessment-2.md`, `-3.md`, and so on. Reports are append-only history — a new run
creates a new file rather than overwriting a prior one, so the trajectory of the project stays
diffable.

## Format

Each report follows the contract in
`specs/001-repo-self-assessment/contracts/assessment-report.md`:

1. Capability inventory (categorized, with evidence paths and maturity)
2. Gaps vs the project goal
3. Source-of-truth discrepancies
4. Recommended next features (ranked by impact-to-effort, one top pick)
5. Write-boundary self-check (`git status` confirmation that only allowed paths changed)

## How to generate one

```
@agent-pm assess the repository and recommend the next feature to build
```

See `specs/001-repo-self-assessment/quickstart.md` for invocation variants and validation steps.
