---
description: "Task list for 008-decouple-analysis-scripts"
---

# Tasks: Decouple the Analysis Pipeline from the Scraper

**Input**: Design documents from `/specs/008-decouple-analysis-scripts/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/analysis-cli.md

**Tests**: No framework configured (constitution III). Verification is import-isolation +
`det_id` byte-stability + output-equality checks (see `quickstart.md`), reusing the existing
synthetic harness `specs/006-analyze-docs-agent/fixtures/build_and_verify.py`.

**Organization**: by priority slice. **US1 (P1)** is the MVP and shippable alone; **US2 (P2)** and
**US3 (P3)** build on it in order. Behavior-preserving throughout — no output/contract change.

## Format: `[ID] [P?] [Story] Description`

## Path Conventions

Python tooling under `scripts/`: `scraper/` (scraping), `scraper/analise/` (analysis), `scraper/utils.py`
(shared). Target P3 layout: `scripts/{common,scraper,analysis}/`.

---

## Phase 1: Setup (verification baselines)

**Purpose**: capture pre-refactor behavior so every slice can prove it changed nothing.

- [x] T001 Capture baselines (not committed): record `det_id` output for a fixed input set (e.g. `det_id("doc_analysis","abc")`, `det_id("alert","x")`) and the `NAMESPACE` value; and snapshot a sample period's analysis output — run `apply-extractions`/`analyze`/`mismatches` for one period (or the synthetic fixture) and save the resulting `document_analyses`/`alerts`/summary to a scratch file for later diffing.

---

## Phase 2: Foundational

**Purpose**: none — the slices are self-contained and sequential by priority; there is no shared
blocking work beyond the Phase 1 baselines. Proceed to US1.

---

## Phase 3: User Story 1 - Run analysis without the scraping stack (Priority: P1) 🎯 MVP

**Goal**: analysis commands import and run with no Playwright; scraping unchanged.

**Independent Test**: with Playwright absent, `python3 -m scraper docs-plan|apply-extractions|analyze|mismatches` run; `scrape -h` works where Playwright is present; outputs identical to baseline.

### Implementation for User Story 1

- [x] T002 [US1] In `scripts/scraper/__main__.py`, remove the top-level `from .runner import run_download_docs, run_scrape` and import `run_scrape`/`run_download_docs` **inside** the `scrape` and `download-docs` argparse handlers in `main()` (the `args.command == "scrape"` / `"download-docs"` branches).
- [x] T003 [US1] In `scripts/scraper/__main__.py` `interactive()`, import `run_scrape`/`run_download_docs` inside the two branches that call them (the "Scrape periods" and "Download documents" menu actions), so the interactive path also avoids the top-level scraper import.
- [x] T004 [US1] Verify US1: in an environment without Playwright, confirm the four analysis commands run and `python3 -c "import scraper.analise.extractions"` succeeds; confirm `scrape -h`/`download-docs -h` still import where Playwright is present; re-run the synthetic harness and confirm outputs + `det_id` sample match the T001 baseline.

**Checkpoint**: analysis runs Playwright-free; shippable as its own PR.

---

## Phase 4: User Story 2 - A dedicated analysis entrypoint (Priority: P2)

**Goal**: analysis is invoked through its own entrypoint (per-command console scripts + a `python -m scraper.analise` dispatcher); callers/docs updated; one obvious way to run each op.

**Independent Test**: each command run via the new entrypoint matches the old `scraper <cmd>` behavior; no stale `scraper <analysis-cmd>` references remain.

### Implementation for User Story 2

- [ ] T005 [US2] Add `scripts/scraper/analise/cli.py`: a shared arg-parser helper for the common flags (`--periodo`/`--data-dir`/`--min-amount`/`--limit`/`--reanalyze`/`--document-id`/`--entry-id`) plus a thin `main()` per command (`docs_plan_main`, `apply_main`, `analyze_main`, `mismatches_main`) delegating to the existing `plan_extractions`/`apply_extractions`/`run_analysis`/`summarize_mismatches` (per `contracts/analysis-cli.md`).
- [ ] T006 [US2] Add `scripts/scraper/analise/__main__.py` dispatcher so `python -m scraper.analise <command>` works (argparse subcommands over `cli.py`), giving a single `--help` overview.
- [ ] T007 [P] [US2] Declare console scripts in `scripts/pyproject.toml` `[project.scripts]`: `docs-plan`/`apply-extractions`/`analyze`/`mismatches` → the `analise.cli` mains.
- [ ] T008 [US2] Remove the analysis subcommands (`analyze`, `docs-plan`, `apply-extractions`, `mismatches`) from `scripts/scraper/__main__.py` so the scraper CLI is `scrape`/`download-docs` only (one obvious analysis path); drop the now-unused `from .analise … import` from `__main__`.
- [ ] T009 [P] [US2] Update callers + docs to the analysis entrypoint: `classify-period` skill (the `docs-plan` call), `analyze-docs` agent (`apply-extractions`/`analyze`/`mismatches`), `scripts/README.md` (Document-analysis section + workflow), and the CLAUDE.md document-analysis bullet.
- [ ] T010 [US2] Verify US2: each operation via the new entrypoint matches baseline; `grep -rn "scraper docs-plan\|scraper apply-extractions\|scraper analyze\|scraper mismatches" .claude/ scripts/README.md CLAUDE.md` returns nothing (SC-006).

**Checkpoint**: analysis has its own entrypoint; scraper CLI no longer hosts analysis.

---

## Phase 5: User Story 3 - Independent scraper and analysis packages (Priority: P3)

**Goal**: `common` leaf + independent `scraper`/`analysis` packages in a uv workspace; analysis carries no Playwright dep; ids byte-stable.

**Independent Test**: install/run `analysis` with no Playwright in its deps; `det_id` byte-identical to baseline; scraper + `import-to-d1` unchanged.

### Implementation for User Story 3

- [ ] T011 [US3] Create `scripts/common/` package containing `det_id`, `NAMESPACE`, `now_ms` moved verbatim from `scraper/utils.py` (byte-identical `NAMESPACE`); leave a thin re-export or remove `utils.py` once callers are repointed.
- [ ] T012 [US3] Repoint the scraping side to `common`: update `scraper/runner.py` (and any other `scraper/*` users of `utils`) to import `det_id`/`now_ms` from `common`.
- [ ] T013 [US3] Move `scripts/scraper/analise/` → `scripts/analysis/`; update intra-package imports (`..utils`/`...utils` → `common`) and the entrypoint/console-script targets (`scraper.analise.*` → `analysis.*`, `python -m analysis`).
- [ ] T014 [US3] Make `scripts/pyproject.toml` a uv workspace with members `common`, `scraper`, `analysis`: `analysis` depends on `common` only (stdlib, no Playwright); `scraper` on `common` + `playwright`; re-lock (`uv lock`).
- [ ] T015 [P] [US3] Update remaining references to the moved package: the `analyze-docs` agent / `classify-*` skills if they name `scraper.analise`, `scripts/README.md`, CLAUDE.md, and the fixture import in `specs/006-analyze-docs-agent/fixtures/build_and_verify.py` (`from scraper.analise…` → `from analysis…`).
- [ ] T016 [US3] Verify US3: in an env where `analysis`'s deps are installed but Playwright is **not**, the full analysis flow runs; `det_id` sample byte-identical to T001 baseline; `scrape -h` works in the scraper env; `node scripts/import-to-d1.mjs --dry-run` produces unchanged SQL; synthetic harness passes.

**Checkpoint**: clean `common`/`scraper`/`analysis` boundary; analysis installable Playwright-free.

---

## Phase 6: Polish & Cross-Cutting

- [ ] T017 Run the full `quickstart.md` verification (import isolation, det_id stability, output equality, scraper/import smoke) and confirm SC-001..SC-006.
- [ ] T018 [P] Final consistency pass: `scripts/README.md`, CLAUDE.md, and `contracts/analysis-cli.md` all describe the same (final) entrypoint; no stale `scraper <analysis-cmd>` or `scraper.analise` references remain.

---

## Dependencies & Execution Order

- **Setup (P1 baselines)** → **US1** → **US2** → **US3** → **Polish**. The slices are sequential by
  priority (US2's entrypoint assumes US1's clean import; US3 relocates what US2 created) and each is
  independently shippable — you may stop after any checkpoint.
- Within US2: T005 → T006 → T008 (cli/dispatcher before removing from scraper CLI); T007 [P] and
  T009 [P] can proceed alongside once the cli mains exist; T010 last.
- Within US3: T011 → T012 (repoint scraper) and T011 → T013 (repoint analysis) → T014 (workspace) →
  T015 [P] (stragglers) → T016 (verify).

## Implementation Strategy

- **MVP = US1 alone**: the lazy-import change delivers "analysis without Playwright" at near-zero
  risk — ship it as its own PR if desired.
- **Then US2**, **then US3**, each a behavior-preserving step gated by the verification checks. The
  one invariant to watch at every step: `det_id`/`NAMESPACE` stays a single shared implementation so
  ids never churn (FR-004 / SC-003).

## Notes

- Do NOT change `data/scrape/<period>.json` shapes, `document_analyses`/`alerts`/`mismatches` output,
  or `scripts/import-to-d1.mjs` — compatibility with them is the core invariant (FR-003/FR-006).
- `.claude` is Prettier-ignored; keep `scripts/README.md` Prettier-clean.
- Commit per slice (US1 / US2 / US3) so each behavior-preserving step is reviewable on its own.
