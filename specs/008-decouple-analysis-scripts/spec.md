# Feature Specification: Decouple the Analysis Pipeline from the Scraper

**Feature Branch**: `008-decouple-analysis-scripts`
**Created**: 2026-06-07
**Status**: Draft
**Input**: User description: "Refactor scripts/ so the analysis pipeline is decoupled from the scraper — analysis commands and the classify-* skills / analyze-docs agent should run without the Playwright scraping stack. Behavior-preserving."

## Overview

The Python under `scripts/` does two unrelated jobs: **scraping** (Playwright browser automation that
produces the period JSON) and **analysis** (reading that JSON to classify documents, reconcile, and
surface mismatches/alerts). Today they're entangled at one point: the CLI entrypoint
(`scraper/__main__.py`) imports the Playwright-based scraping code at module load, so **every**
analysis command (`docs-plan`, `apply-extractions`, `analyze`, `mismatches`) drags in the full
scraping stack — even though the analysis subpackage is already import-clean (stdlib-only), the
scraping side never imports analysis, and the only shared code is `scraper/utils.py`
(`det_id`/`NAMESPACE`, `now_ms`).

The dependency graph is a clean near-DAG: a shared `utils` leaf, two independent subsystems (scraper
= Playwright; analysis = stdlib-only), joined only by the CLI. This feature untangles them so the
analysis pipeline — and the `classify-*` skills / `analyze-docs` agent that drive it — runs without
the Playwright/scraping environment. It is **behavior-preserving**: no change to `document_analyses`/
`alerts` shapes, the mismatch summary, the period-JSON contract, the `import-to-d1` flow, or the
deterministic grouping / roll-up / reconciliation / duplicate-billing logic.

> **Scope note (implementation).** US2 and US3 were delivered as one simplified slice: a **plain
> folder split** (`scripts/{common,scraper,analysis}/`, run via `python -m`, one venv, no
> packaging change). The "independent dependency sets" / installable-standalone aspect of US3
> (FR-007, SC-005) and the console-script entrypoints were **descoped** — they only buy a standalone
> install and bare command names, neither needed to run analysis here without the scraper. The
> achieved decoupling (analysis imports/runs with no Playwright) fully satisfies the core goal. See
> `plan.md` (Scope update) and `tasks.md`.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Run analysis without the scraping stack (Priority: P1) 🎯 MVP

A maintainer (or CI, or the skills/agent) runs an analysis command on a machine that does **not**
have the scraping dependencies (Playwright/browser) installed. The command runs successfully because
analysis no longer imports the scraping code.

**Why this priority**: This is the core pain and the cheapest, highest-value fix — analysis becomes
runnable in a minimal/CI environment and the agent/skills stop paying the scraping-stack cost. It is
independently shippable on its own.

**Independent Test**: In an environment without Playwright installed, run each analysis command
(`docs-plan`, `apply-extractions`, `analyze`, `mismatches`) and confirm it works; confirm the
scraping commands still work where the scraping deps are present.

**Acceptance Scenarios**:

1. **Given** an environment with no Playwright installed, **When** an analysis command is run,
   **Then** it completes normally (no import error for the scraping stack).
2. **Given** the scraping environment, **When** `scrape`/`download-docs` are run, **Then** they work
   exactly as before.
3. **Given** any analysis command, **When** it runs, **Then** its output (period-JSON writes, the
   mismatch summary) is identical to before this change.

---

### User Story 2 - A dedicated analysis entrypoint (Priority: P2)

The `classify-*` skills and the `analyze-docs` agent invoke the analysis pipeline through an
entrypoint that is clearly the *analysis* tool, not the scraper CLI. The skills/agent/docs are
updated to use it.

**Why this priority**: Removes the conceptual coupling (analysis-as-a-scraper-subcommand) and lets
the analysis callers depend on the analysis tool alone. Builds on US1.

**Independent Test**: Invoke each analysis operation via the dedicated entrypoint and confirm the
same result as the old `scraper <cmd>` path; confirm the skills/agent reference the new entrypoint.

**Acceptance Scenarios**:

1. **Given** the dedicated analysis entrypoint, **When** a maintainer runs each analysis operation
   through it, **Then** the behavior matches the previous `scraper <cmd>` invocation.
2. **Given** the updated skills/agent/docs, **When** they invoke analysis, **Then** they call the
   analysis entrypoint, not the scraper CLI.
3. **Given** the old invocation path, **When** it is removed/redirected, **Then** there is one
   obvious way to run analysis and the docs reflect it.

---

### User Story 3 - Independent scraper and analysis packages (Priority: P3)

Scraping and analysis live in separate packages with their own dependency sets — scraper carries the
Playwright deps; analysis is stdlib-only — sharing only a small `common` leaf (`det_id`/`NAMESPACE`,
`now_ms`). Deterministic ids remain stable across the change.

**Why this priority**: The clean long-term boundary (independent install/test/ownership), but the
biggest move and only worthwhile once US1/US2 prove the seam. Carries the most risk (packaging, id
stability), so it ships last.

**Independent Test**: Build/install the analysis package alone (without the scraper's deps) and run
the full analysis flow; confirm `det_id`-derived ids are byte-identical to before; confirm the
scraper package still works.

**Acceptance Scenarios**:

1. **Given** the split, **When** the analysis package is installed without the scraper's deps,
   **Then** the full analysis flow runs.
2. **Given** the shared `common` leaf, **When** both packages use `det_id`, **Then** ids are
   byte-identical to the pre-split implementation (no id churn) — the `NAMESPACE` is unchanged.
3. **Given** the split, **When** the scraper runs, **Then** it produces the same period JSON, and
   `import-to-d1` ingests analysis output unchanged.

### Edge Cases

- **A command that legitimately needs both** (if any combined scrape→analyze flow exists): it must
  still work, importing both subsystems explicitly rather than implicitly.
- **`det_id` namespace drift**: if the shared util were duplicated instead of shared, ids would
  silently diverge — the split must keep a single `NAMESPACE`/implementation.
- **Stale references**: any docs/skills/agent/CI path that calls the old `scraper <analysis-cmd>`
  form must be updated; a missed reference would break those callers.
- **Lockfile/dependency**: removing Playwright from the analysis dependency set must not break the
  scraper's resolution, and vice versa.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: Running any analysis command (`docs-plan`, `apply-extractions`, `analyze`,
  `mismatches`) MUST NOT require the scraping (Playwright/browser) dependencies to be importable.
- **FR-002**: The scraping commands (`scrape`, `download-docs`) MUST continue to work unchanged where
  the scraping dependencies are present.
- **FR-003**: The refactor MUST be behavior-preserving: `document_analyses` / `analysis_records` /
  `alerts` shapes, the `mismatches` summary, the period-JSON contract, and the deterministic
  grouping / roll-up / reconciliation / duplicate-billing logic MUST be unchanged.
- **FR-004**: `det_id`-derived identifiers MUST remain byte-identical after the refactor (the
  `NAMESPACE` constant and `det_id` semantics are preserved); there MUST be exactly one shared
  implementation, not duplicated copies.
- **FR-005**: The analysis pipeline MUST be invocable through an entrypoint that does not route
  through the scraper CLI, and the `classify-*` skills, `analyze-docs` agent, and docs MUST be
  updated to use it.
- **FR-006**: `scripts/import-to-d1.mjs` and the D1 import flow MUST continue to work with no change
  (it reads the period JSON, which is unchanged).
- **FR-007** (P3): Scraping and analysis MUST be separable into independent packages with their own
  dependency sets — analysis stdlib-only, scraper carrying Playwright — sharing only the `common`
  leaf. The packaging change MUST NOT alter runtime behavior or outputs.
- **FR-008**: Any combined flow that needs both subsystems MUST import them explicitly, so that no
  analysis-only path transitively imports the scraping stack.

### Key Entities *(include if feature involves data)*

- **Shared `common` leaf**: the minimal code both subsystems depend on — `det_id` (+ the fixed
  `NAMESPACE`) and `now_ms`. The only shared surface.
- **Scraper subsystem**: Playwright-based browser automation + extractors that produce the period
  JSON. Depends on `common` and the scraping deps.
- **Analysis subsystem**: the stdlib-only pipeline (`loader`, `models`, `documentos`, `nf_groups`,
  `extractions`, `checks`) that reads/writes the period JSON and emits analyses/alerts/mismatches.
  Depends only on `common`.
- **Period JSON contract**: the `<period>.json` data shape both subsystems agree on (scraper writes
  it; analysis reads/augments it; `import-to-d1` ingests it) — an implicit contract preserved
  throughout.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: With the scraping dependencies absent, all four analysis commands run to completion;
  before this change at least one of them fails to import.
- **SC-002**: For identical inputs, analysis outputs (period-JSON `document_analyses`/`alerts`, the
  `mismatches` summary) are byte-equivalent to pre-refactor output.
- **SC-003**: `det_id` produces byte-identical ids for the same inputs before and after the refactor
  (verified on a representative set) — zero id churn.
- **SC-004**: The scraping commands and `scripts/import-to-d1.mjs` behave identically to before.
- **SC-005** (P3): The analysis package can be installed and run with **no** Playwright/browser
  dependency in its dependency set.
- **SC-006**: There is exactly one documented way to run each analysis operation, and every skill /
  agent / doc reference points at it (no stale `scraper <analysis-cmd>` references remain).

## Assumptions

- The analysis subpackage (`scraper/analise`) is already import-clean (stdlib-only) and the scraping
  side does not import it — verified; the only cross-boundary import is `analise → ..utils`.
- The work is staged P1 → P2 → P3 and may stop after any slice; P1 alone delivers the core value
  (analysis without Playwright) at near-zero risk.
- No change to the period-JSON schema, the D1 schema, or `import-to-d1.mjs` is intended or required.
- Packaging in P3 uses the project's existing Python tooling (uv); the exact layout (uv workspace vs.
  separate projects) is an implementation/plan decision, not a spec constraint.
- This is a pure refactor: no new analysis features, no behavior change — only the module/dependency
  boundary and entrypoint move.
