# Contract: Hand-off Feature Description

When the maintainer accepts a recommendation, the PM agent MUST write a file in this shape so a
*separate* spec-running agent can begin `speckit specify` without any access to the PM session.
This is the output contract for FR-008, FR-015, SC-006, and Acceptance US3-1/US3-2.

- **Path**: `specs/_handoff/<slug>.md` (`slug` = kebab-case feature name)
- **Format**: Markdown with a small YAML frontmatter block for machine consumption

## Template

```markdown
---
slug: <kebab-case-name>
title: <Feature title>
status: pending
source_report: docs/assessments/<YYYY-MM-DD>-assessment.md
created: <YYYY-MM-DD>
---

# <Feature title>

## Summary

<One self-contained paragraph describing the feature — phrased so it can be passed directly as
the argument to `speckit specify`. No references to "the assessment above" or PM-session context.>

## Problem & Goal Link

<The gap this closes and how it advances the project goal (correctness verification / forgery &
corruption detection). Cite the relevant docs/SCOPE-fraud-detection.md phase if applicable.>

## Scope Notes

- **In scope**: <bullets>
- **Out of scope (for now)**: <bullets>
- **Depends on**: <existing capabilities / data / endpoints>
- **Suggested first slice (MVP)**: <the smallest valuable increment>
```

## Contract rules

1. The file MUST be self-contained — a separate agent reading only this file has enough to run
   `speckit specify` (SC-006, Acceptance US3-2).
2. `status` starts as `pending`. (The spec-running agent owns any later status changes; the PM
   agent does not implement.)
3. `source_report` MUST link back to the originating assessment report.
4. Writing this file MUST NOT modify any application code, schema, or data (FR-007, SC-005); the
   only new/changed paths are this file and the assessment report.
5. One hand-off file corresponds to exactly one accepted recommendation.

## Consumer note (separate spec-running agent)

The downstream agent is expected to:
1. Read `specs/_handoff/<slug>.md`.
2. Run `speckit specify` using the `Summary` (and `Scope Notes`) as the feature description.
3. Optionally move/mark the hand-off file as consumed once a real `specs/<NNN>-<slug>/` exists.

This consumer behavior is out of scope for THIS feature (which only delivers the PM agent and the
hand-off artifact); it is documented here so the contract is unambiguous at the boundary.
