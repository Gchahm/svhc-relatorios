# Implementation Plan: Decouple the Analysis Pipeline from the Scraper

**Branch**: `008-decouple-analysis-scripts` | **Date**: 2026-06-07 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/008-decouple-analysis-scripts/spec.md`

## Summary

Untangle the two jobs under `scripts/` — Playwright **scraping** and stdlib-only **analysis** — which
today are coupled only at the CLI entrypoint (`scraper/__main__.py` imports `runner` → `browser` →
`playwright` at module load, so every analysis command needlessly drags in the scraping stack). The
analysis subpackage (`scraper/analise`) is already import-clean and the scraping side never imports
it; the only shared code is `scraper/utils.py` (`det_id`/`NAMESPACE`, `now_ms`). Deliver in three
staged, independently-shippable slices: **P1** lazy-import the scraper-only modules so analysis runs
without Playwright; **P2** a dedicated analysis entrypoint the skills/agent call; **P3** a full
package split (`common` leaf + independent `scraper`/`analysis` packages with their own deps).
Behavior-preserving throughout: no change to `document_analyses`/`alerts` shapes, the `mismatches`
summary, the period-JSON contract, `import-to-d1`, or the deterministic logic — and `det_id` ids stay
byte-identical.

## Technical Context

**Language/Version**: Python 3.12+ (`scripts/`), managed by `uv`.
**Primary Dependencies**: scraper = `playwright` + `python-dotenv`; analysis = **stdlib only**
(`json`, `pathlib`, `hashlib`, `re`, `argparse`, `uuid`, `datetime`). The refactor's goal is to make
that dependency boundary real.
**Storage**: period JSON under `data/scrape/<YYYY-MM>.json` (source of truth); intermediate working
files `<period>.extract-todo.json` and `<image>.classify.json` (gitignored). D1 downstream via
`scripts/import-to-d1.mjs` (unchanged).
**Testing**: no framework (constitution III — tests OPTIONAL). Verification = import checks (analysis
without Playwright), a `det_id` byte-stability check, and analysis-output equality on a sample period.
**Target Platform**: local dev / CI running Python; analysis must run with no browser stack.
**Project Type**: single repo, Python tooling under `scripts/` (plus the Next.js app, untouched).
**Performance Goals**: not a perf change; secondary win is faster analysis startup (no Playwright
import / no browser-deps sync).
**Constraints**: behavior-preserving; `det_id`/`NAMESPACE` single shared implementation (no id churn);
period-JSON + D1 import contract unchanged; `classify-*` skills / `analyze-docs` agent keep working.
**Scale/Scope**: ~a dozen Python modules; one CLI entrypoint; one shared util file to relocate (P3).

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- **I. Type Safety & Schema Discipline** — PASS. Python-only refactor; no TypeScript, no Drizzle/D1
  schema change. The period-JSON and `document_analyses` shapes are explicitly preserved (FR-003).
- **II. Cloudflare-Native Architecture** — PASS / N/A. Offline ingestion/analysis tooling; no Workers
  bindings or `getDb()` involved.
- **III. Quality Gates Before Commit** — PASS. `pnpm lint`/`pnpm format` cover TS (untouched); the
  touched `scripts/README.md` stays Prettier-clean; `.claude` is Prettier-ignored. Tests OPTIONAL —
  verification is the import/`det_id`/output-equality checks below.
- **IV. Security & Auth by Default** — PASS / N/A. No routes, no secrets; scraper `.env` handling
  unchanged.
- **V. Simplicity & Incremental Delivery** — PASS. The refactor **reduces** coupling and removes a
  needless dependency from the analysis path. Delivered as prioritized, independently-shippable
  slices (P1 near-zero-risk; P2/P3 optional). P3 adds packaging surface (a `common` leaf + workspace),
  justified by the concrete need (analysis installable/runnable without Playwright) — recorded below,
  not a violation.

**Result**: No violations. Complexity Tracking left empty.

## Project Structure

### Documentation (this feature)

```text
specs/008-decouple-analysis-scripts/
├── plan.md              # This file
├── research.md          # Phase 0 — decisions (lazy-import, entrypoint shape, P3 layout, det_id)
├── data-model.md        # Phase 1 — module→package mapping + preserved contracts (no data change)
├── quickstart.md        # Phase 1 — run analysis w/o Playwright + verification (det_id, output eq)
├── contracts/
│   └── analysis-cli.md  # the analysis command surface (stable across the entrypoint move)
├── checklists/requirements.md
└── tasks.md             # Phase 2 (speckit tasks — not created here)
```

### Source Code — current vs. target

```text
# CURRENT
scripts/
├── pyproject.toml            # one project: playwright + python-dotenv
└── scraper/
    ├── __main__.py           # CLI: scrape/download-docs (Playwright) + analyze/docs-plan/
    │                         #   apply-extractions/mismatches (analysis) — TOP-LEVEL runner import
    ├── runner.py, browser.py, config.py, extractors/   # scraping (Playwright)
    ├── utils.py              # SHARED leaf: det_id/NAMESPACE, now_ms
    └── analise/              # analysis (stdlib only): loader, models, documentos, nf_groups,
                              #   extractions, reporter, checks/

# TARGET (after P3)
scripts/
├── pyproject.toml            # uv workspace root: members = common, scraper, analysis
├── common/                   # det_id/NAMESPACE, now_ms  (stdlib only; the only shared code)
├── scraper/                  # scraping CLI + runner/browser/config/extractors; deps: common + playwright
└── analysis/                 # (was scraper/analise) analysis CLI + pipeline; deps: common ONLY (stdlib)
```

**Structure Decision**: keep everything under `scripts/` (single repo). P1/P2 make no physical moves
(lazy import + a new entrypoint). P3 promotes `scraper/analise` → top-level `analysis`, extracts
`utils` → `common`, and turns `scripts/` into a uv workspace so `analysis` carries no Playwright dep.

## Staged approach

### P1 — Lazy-import the scraper stack (US1) — MVP, near-zero risk

- In `scraper/__main__.py`, drop the top-level `from .runner import run_download_docs, run_scrape`
  (line 22). Import `runner` **inside** the branches that need it: the `scrape`/`download-docs`
  argparse handlers in `main()`, and the two `interactive()` branches that call `run_scrape`/
  `run_download_docs`. Everything analysis (`from .analise …`) stays top-level (already clean).
- Result: `python -m scraper docs-plan|apply-extractions|analyze|mismatches` imports only `analise`
  (stdlib) — no Playwright. Scrape/download unchanged.
- Verify: in an env without Playwright, the four analysis commands run; `scrape -h` still works where
  Playwright is present.

### P2 — Dedicated analysis entrypoint (US2)

- Add an analysis entrypoint that doesn't route through the scraper CLI (design in research.md;
  chosen: per-command console scripts backed by a small `analise/cli` module, plus a
  `python -m scraper.analise` dispatcher for discoverability). Update the `classify-period` skill,
  `analyze-docs` agent, `scripts/README.md`, and CLAUDE.md to call it.
- The command surface (names + args) is fixed by `contracts/analysis-cli.md`, so callers are stable
  whether invoked via the scraper CLI (today) or the analysis entrypoint (after P2).

### P3 — Independent packages (US3)

- Extract `scraper/utils.py` → a `common` package (keep `NAMESPACE`/`det_id` byte-identical).
- Move `scraper/analise` → top-level `analysis` package; update intra-imports (`..utils` → `common`).
- Make `scripts/` a uv workspace with members `common`, `scraper`, `analysis`; `analysis` depends on
  `common` only (no Playwright), `scraper` on `common` + `playwright`.
- Verify: install/run `analysis` with no Playwright in its dep set; `det_id` byte-stable; scraper +
  `import-to-d1` unchanged.

## Verification strategy (behavior-preserving)

1. **Import isolation**: `python3 -c "import scraper.analise..."` (and post-P3 `import analysis...`)
   succeeds with Playwright absent; the analysis commands run.
2. **`det_id` stability**: a tiny check that `det_id(...)` for a fixed set of inputs is byte-identical
   before and after each slice (guards FR-004/SC-003 across the `utils`→`common` move).
3. **Output equality**: run `apply-extractions` + `analyze` + `mismatches` on a sample period from
   identical `.classify.json` inputs, before vs. after, and diff `document_analyses`/`alerts`/summary.
4. **Scraper + import smoke**: `scrape -h`/`download-docs -h` import cleanly with Playwright present;
   `import-to-d1 --dry-run` over a sample produces unchanged SQL.

## Complexity Tracking

> No constitution violations — no entries required.

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|--------------------------------------|
| (none)    | —          | —                                    |
