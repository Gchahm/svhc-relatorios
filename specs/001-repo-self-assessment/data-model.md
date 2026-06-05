# Phase 1 Data Model: Repository Self-Assessment & Next-Feature Recommendation

These are **content models** for the artifacts the PM agent produces — not database tables. There
is no persistence layer beyond Markdown files on disk. Each model lists its fields, allowed
values, and validation rules derived from the functional requirements.

## Entity: Capability Inventory

A structured snapshot of what the project does today (FR-002, FR-003).

| Field | Type | Notes |
|-------|------|-------|
| `category` | enum-ish string | e.g. Ingestion/Scraping, Data Model, Auditing Checks, Reporting, Auth, UI/Dashboard, Infra |
| `name` | string | Short capability name |
| `maturity` | enum | `complete` \| `partial` \| `stub` \| `planned` |
| `evidence` | string | Concrete location — path(s) like `src/app/api/alerts/`, `src/db/fiscal.schema.ts`, `scripts/scraper/` |

**Validation rules**:
- Every item MUST have non-empty `evidence` pointing to a real path/artifact (FR-002).
- `maturity` MUST be one of the four enum values (FR-003).
- The inventory SHOULD cover ≥90% of significant existing capabilities (SC-002).
- A capability present in code MUST appear (Acceptance US1-2).

## Entity: Project Goal Model

The reference standard the inventory is measured against (FR-004, FR-010).

| Field | Type | Notes |
|-------|------|-------|
| `northStar` | string | Verify correctness of scraped fiscal data/docs; detect forgery/corruption |
| `goalSource` | path | Canonical: `docs/SCOPE-fraud-detection.md` (phases 1–4) |
| `runFocus` | string \| null | Optional maintainer-supplied focus for this run; null = full goal |

**Validation rules**:
- When `runFocus` is set, recommendations MUST honor it while relating it back to `northStar`
  (FR-010, "goal drift" edge case).

## Entity: Gap

A discrepancy between current capabilities and the goal (FR-004).

| Field | Type | Notes |
|-------|------|-------|
| `description` | string | What is missing or insufficient |
| `severity` | enum | `high` \| `medium` \| `low` — criticality to the goal |
| `affectedArea` | string | Capability category the gap sits in |
| `goalLink` | string | Which goal phase/aspect it blocks (e.g. "SCOPE Phase 2: CNPJ validation") |

**Validation rules**:
- Each Gap MUST reference the goal aspect it relates to (FR-004).
- If no high-value gap exists, the report MUST say so rather than inventing one (FR-013).

## Entity: Feature Recommendation

A proposed next feature (FR-005, FR-006).

| Field | Type | Notes |
|-------|------|-------|
| `title` | string | Concise feature name |
| `gapClosed` | ref → Gap | The gap this addresses |
| `rationale` | string | Why it advances the project goal |
| `impact` | enum | `high` \| `medium` \| `low` (+ one-line justification) |
| `effort` | enum | `high` \| `medium` \| `low` (+ one-line justification) |
| `dependencies` | string[] | Existing capabilities it depends on |
| `rank` | integer | Position in the shortlist (1 = best impact-to-effort) |
| `isTopPick` | boolean | Exactly one recommendation per run is `true` |

**Validation rules**:
- Shortlist is ordered by impact-to-effort ratio; ties broken by Gap `severity` (R5, FR-005).
- Exactly ONE candidate has `isTopPick = true` (FR-005).
- Every candidate MUST include all of: `gapClosed`, `rationale`, `impact`, `effort`,
  `dependencies` (FR-006, SC-003 — 100%).

## Entity: Assessment Report

The persisted, dated artifact for a single run (FR-014). See
`contracts/assessment-report.md` for the exact layout.

| Field | Type | Notes |
|-------|------|-------|
| `runDate` | date | `YYYY-MM-DD`; part of the filename |
| `runFocus` | string \| null | Echoed from the Project Goal Model |
| `inventory` | Capability Inventory[] | The full categorized inventory |
| `gaps` | Gap[] | Identified gaps |
| `recommendations` | Feature Recommendation[] | The ranked shortlist |
| `discrepancies` | string[] | Source-of-truth conflicts found (FR-009) |
| `writeBoundaryCheck` | string | Result of the `git status` self-check (R7) |

**Storage**: `docs/assessments/<runDate>-assessment.md` (suffix `-2`, `-3`… on same-day repeats).

## Entity: Hand-off Feature Description

The self-contained description of an accepted recommendation, written for a separate
spec-running agent (FR-008, FR-015). See `contracts/handoff-feature.md`.

| Field | Type | Notes |
|-------|------|-------|
| `slug` | string | kebab-case; becomes the filename |
| `title` | string | Feature title |
| `summary` | string | One-paragraph description suitable as `speckit specify` input |
| `problemAndGoalLink` | string | The gap it closes + tie to the project goal |
| `scopeNotes` | string | In/out-of-scope hints, dependencies, suggested first slice |
| `sourceReport` | path | Link back to the originating assessment report |
| `status` | enum | `pending` (default when written) |

**Storage**: `specs/_handoff/<slug>.md`. The `_handoff` prefix keeps it out of speckit's
`^[0-9]{3}-` glob.

**Validation rules**:
- MUST be self-contained — readable by a separate agent with no access to the PM session (SC-006,
  Acceptance US3-2).
- Writing it MUST NOT alter any application file (FR-007, SC-005).

## Relationships

```text
Project Goal Model ──measured-against──> Capability Inventory
        │                                       │
        └──────────────> Gap <─────────────────┘   (gaps = goal − capabilities)
                          │
                          ▼
              Feature Recommendation (ranked by impact/effort)
                          │  isTopPick = true, accepted by maintainer
                          ▼
              Hand-off Feature Description  ──consumed-by──> separate speckit agent

All of {Inventory, Gaps, Recommendations} are captured in one Assessment Report per run.
```
