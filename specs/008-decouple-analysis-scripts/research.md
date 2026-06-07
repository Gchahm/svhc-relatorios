# Phase 0 Research: Decouple the Analysis Pipeline from the Scraper

Evidence-based decisions for the refactor. No open NEEDS CLARIFICATION items — the dependency graph
was measured directly (see Decision 0).

## Decision 0 — The coupling is one edge; the rest is already clean (measured)

- `scraper/analise/**` imports from the parent only `..utils` (`det_id`/`now_ms`). It imports cleanly
  with **no Playwright**.
- The scraping side (`runner`/`browser`/`config`/`extractors`) imports `analise`: **never**.
- The only thing that pulls both together is `scraper/__main__.py`, whose **top-level**
  `from .runner import …` (line 22) drags `browser` → `playwright` into every invocation, including
  analysis-only commands.

**Implication**: a near-DAG (`utils` leaf ← {scraper, analise}, joined at the CLI). The whole feature
is "cut the one needless edge", staged by how thoroughly.

## Decision 1 — P1: lazy-import, don't restructure

**Decision**: move `from .runner import run_download_docs, run_scrape` out of the module top and into
the `scrape`/`download-docs` code paths (argparse handlers + the two `interactive()` branches). Leave
the analysis imports top-level (already clean).

**Rationale**: ~3-line change, zero behavior change, immediately makes the four analysis commands
runnable with no Playwright. Highest value-per-risk; ships alone.

**Alternatives**: split packages first (P3) — rejected as the *first* step (big move, more risk,
unnecessary to get the core win).

## Decision 2 — P2: per-command console scripts + a dispatcher

**Decision**: expose the analysis operations as **console-script entrypoints per command** declared
in `pyproject.toml` `[project.scripts]` (`docs-plan`, `apply-extractions`, `analyze`, `mismatches`),
each a thin `main()` over a **shared arg-parser helper** in an `analise/cli` module — and keep a
`python -m scraper.analise <cmd>` dispatcher for the `--help` overview. Callers (`classify-period`
skill, `analyze-docs` agent, docs) use the analysis entrypoint, not the scraper CLI.

**Rationale**: per-command commands read cleanest for the skills/agent shelling out
(`uv run apply-extractions …`) and make each step independently runnable/testable — which fits the
classification loop where steps are invoked individually. A shared arg helper avoids duplicating the
common flags (`--periodo`/`--data-dir`/`--document-id`/`--entry-id`). The dispatcher preserves
discoverability. Keeping them in **one** analysis package (not one package per command) is right —
they share deps, data, and arg code; per-package would be over-engineering.

**Alternatives**: single `analysis <subcommand>` CLI only (more DRY/discoverable, but each op isn't a
standalone command — worse ergonomics for the agent/loop); separate `python -m analysis.<cmd>` modules
(more boilerplate than console scripts). Both viable; console-scripts-per-command chosen for caller
ergonomics. This is an entrypoint-shape choice and is reversible.

## Decision 3 — P3: uv workspace with a `common` leaf

**Decision**: turn `scripts/` into a **uv workspace** with three members:
- `common/` — `det_id`/`NAMESPACE`, `now_ms` (stdlib only; the sole shared code).
- `scraper/` — scraping CLI + `runner`/`browser`/`config`/`extractors`; deps: `common` + `playwright`.
- `analysis/` — the former `scraper/analise`; deps: `common` only (stdlib).

**Rationale**: a workspace gives each member its own dependency set (analysis carries **no**
Playwright) while sharing `common` via a path/workspace dependency — exactly the boundary we want,
with one lockfile and `uv run` resolving members. Promoting `analise` → top-level `analysis` matches
its independence; `import-to-d1.mjs` is untouched (it only reads the period JSON).

**Alternatives**: two fully separate uv projects (more ceremony, two lockfiles, awkward `common`
sharing); leave `analise` nested but give it its own optional-dep group (doesn't achieve a real
no-Playwright install). Workspace chosen as the standard uv way to do exactly this.

## Decision 4 — `det_id` stability is the one hard invariant

**Decision**: `det_id` and its `NAMESPACE = uuid5(NAMESPACE_DNS, "svhc.fiscal")` move verbatim into
`common` — a single shared implementation, never duplicated. A byte-stability check (fixed inputs →
expected uuids) guards every slice that touches `utils`/`common`.

**Rationale**: scraper-minted entity ids and analysis-minted (`doc_analysis`/record/alert) ids are
both derived from this namespace; changing it would silently churn ids and break stable upserts /
joins (`INSERT OR REPLACE` relies on stable ids). The two sides don't cross-derive ids, so sharing is
about *stability*, not cross-correctness — but a single impl is the safe, simple guarantee (FR-004,
SC-003).

## Decision 5 — Verification without new test tooling

**Decision**: verify behavior preservation with (a) import-isolation checks (analysis imports/runs
with Playwright absent), (b) a `det_id` byte-stability check, (c) output-equality of
`document_analyses`/`alerts`/`mismatches` on a sample period from fixed `.classify.json` inputs before
vs. after, and (d) a scraper + `import-to-d1 --dry-run` smoke. No test framework is added (constitution
III); the existing synthetic fixture (`specs/006-…/fixtures/build_and_verify.py`) already exercises the
deterministic merge and can re-run post-refactor as a regression check.

**Rationale**: the refactor must not change outputs; these checks pin exactly that, cheaply, and reuse
what already exists.
