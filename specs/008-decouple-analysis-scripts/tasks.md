---
description: "Task list for 008-decouple-analysis-scripts"
---

# Tasks: Decouple the Analysis Pipeline from the Scraper

**Input**: Design documents from `/specs/008-decouple-analysis-scripts/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/analysis-cli.md

**Tests**: No framework configured (constitution III). Verification = import-isolation +
`det_id` byte-stability + the synthetic harness `specs/006-analyze-docs-agent/fixtures/build_and_verify.py`.

**Organization**: by priority slice. **US1 (P1)** is the dependency-decoupling MVP (done). **US2**
promotes analysis into its own package — the simple folder split with a shared `common` leaf and a
`python -m analysis` entrypoint. **No build-system, no uv workspace, no console scripts** (those were
descoped — see plan.md); everything runs via `python -m` in the existing single venv.

## Format: `[ID] [P?] [Story] Description`

## Path Conventions

Today: `scripts/scraper/` (scraping + `analise/` + `utils.py`). Target: `scripts/{common,scraper,analysis}/`,
all run via `python -m` from `scripts/` (one venv; no packaging change).

---

## Phase 1: Setup (verification baselines)

- [x] T001 Capture baselines (not committed): `det_id` outputs for a fixed input set + the `NAMESPACE` value, and the synthetic-harness pass, so each change can prove it changed nothing.

---

## Phase 2: Foundational

**Purpose**: none — slices are self-contained and sequential. Proceed.

---

## Phase 3: User Story 1 - Run analysis without the scraping stack (Priority: P1) 🎯 MVP — DONE

- [x] T002 [US1] In `scripts/scraper/__main__.py`, drop the top-level `from .runner import …`; lazy-import `run_scrape`/`run_download_docs` inside the `scrape`/`download-docs` argparse handlers.
- [x] T003 [US1] In `interactive()`, lazy-import `run_scrape`/`run_download_docs` inside the scrape/download branches.
- [x] T004 [US1] Verified: analysis commands run under plain `python3` (no Playwright); `det_id` sample byte-identical to baseline; scrape/download still registered; synthetic harness passes.

**Checkpoint**: analysis runs Playwright-free (shipped in PR #11).

---

## Phase 4: User Story 2 - Independent `analysis` package with a shared `common` leaf (Priority: P2)

**Goal**: scraping and analysis live in separate top-level packages sharing only a `common` leaf;
analysis has its own `python -m analysis` entrypoint and never touches the scraper. Plain folders +
`python -m` — no build-system, no workspace. Behavior-preserving; `det_id` ids byte-stable.

**Independent Test**: `python -m analysis <cmd>` runs every analysis op (matching old behavior) with
no scraper import; `python -m scraper` is scrape/download only; `det_id` unchanged; harness passes.

### Implementation for User Story 2

- [x] T005 [US2] Create `scripts/common/__init__.py` containing `det_id`, `NAMESPACE`, `now_ms` moved **verbatim** from `scraper/utils.py` (byte-identical `NAMESPACE` — guards `det_id` stability).
- [x] T006 [US2] Repoint the scraper to `common`: update every `scraper/*` import of `.utils` (at least `scraper/runner.py`) to `from common import …`; delete `scripts/scraper/utils.py` once no references remain (`grep -rn "utils import\|\.utils\b" scripts/scraper`).
- [x] T007 [US2] Move `scripts/scraper/analise/` → `scripts/analysis/`. Fix the cross-boundary imports: `from ..utils` / `from ...utils` → `from common`. Intra-package relative imports (`from .documentos`, `from ..models`, `from ..nf_groups`, `from .checks`) are unchanged.
- [x] T008 [US2] Add `scripts/analysis/__main__.py`: an argparse dispatcher for `docs-plan`/`apply-extractions`/`analyze`/`mismatches` (the command surface in `contracts/analysis-cli.md`) delegating to `run_analysis` (from `analysis`) and `plan_extractions`/`apply_extractions`/`summarize_mismatches` (from `analysis.extractions`), so `python -m analysis <cmd>` works.
- [x] T009 [US2] Strip analysis from `scripts/scraper/__main__.py`: remove the `analyze`/`docs-plan`/`apply-extractions`/`mismatches` subparsers + dispatch branches, the `from .analise …` imports, the now-unused `json` import, and the three analysis actions in `interactive()` — leaving the scraper CLI as `scrape`/`download-docs` only.
- [x] T010 [P] [US2] Update callers + docs to `python -m analysis <cmd>`: the `classify-period` skill (`docs-plan`), the `analyze-docs` agent (`apply-extractions`/`analyze`/`mismatches`), `scripts/README.md`, the CLAUDE.md document-analysis bullet, and the fixture import in `specs/006-analyze-docs-agent/fixtures/build_and_verify.py` (`from scraper.analise…` → `from analysis…`).
- [x] T011 [US2] Verify US2: `det_id` sample byte-identical to T001 baseline; `python -m analysis docs-plan|apply-extractions|analyze|mismatches` run with no scraper/Playwright import; `python -m scraper --help` lists only `scrape`/`download-docs`; run the synthetic harness (passes); `grep -rn "scraper.analise\|scraper docs-plan\|scraper apply-extractions\|scraper mismatches" .claude/ scripts/ specs/006-analyze-docs-agent/` returns nothing.

**Checkpoint**: clean `common`/`scraper`/`analysis` folders; analysis runs via its own entrypoint.

---

## Phase 5: Polish & Cross-Cutting

- [x] T012 Run the `quickstart.md` checks (import isolation, det_id stability, harness, scraper smoke) and confirm SC-001..SC-006; final consistency pass on `scripts/README.md` / CLAUDE.md / `contracts/analysis-cli.md` (all reference `python -m analysis`); no stale `scraper.analise` / `scraper <analysis-cmd>` references remain.

---

## Dependencies & Execution Order

- **Setup → US1 (done) → US2 → Polish.**
- Within US2: **T005** (common) → **T006** (repoint scraper) and **T005 → T007** (move analysis, repoint to common) → **T008** (analysis entrypoint) → **T009** (strip scraper CLI); **T010 [P]** (callers/docs) once the move lands; **T011** verifies.
- The one invariant at every step: `det_id`/`NAMESPACE` is a single shared implementation in `common`, byte-identical to before (FR-004 / SC-003).

## Implementation Strategy

Plain folder split, one venv, `python -m` entrypoints — no packaging change. US2 is a single
behavior-preserving commit gated by T011's checks. (Build-system + console scripts + a uv workspace
with separate dependency sets were considered and **descoped**: they only buy bare command names and
a standalone install, neither needed to run analysis here without the scraper.)

## Notes

- Do NOT change `data/scrape/<period>.json` shapes, `document_analyses`/`alerts`/`mismatches` output,
  or `scripts/import-to-d1.mjs`.
- `pyproject.toml` is unchanged: `python -m analysis`/`python -m scraper` resolve `common`/`analysis`/
  `scraper` as top-level packages because `scripts/` is the run directory. Playwright stays a venv
  dependency but `analysis` never imports it.
