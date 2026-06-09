# Phase 0 Research: Scraper and analysis operate directly on the database

All open questions from the spec were resolved with the operator during `specify`. This document records the *technical* decisions that close the remaining unknowns in the plan's Technical Context, each with rationale and the alternatives weighed.

## D1 access from Python (read + write, local + remote)

- **Decision**: Reach D1 exclusively through the `wrangler` CLI, shelled out from Python. Writes use `wrangler d1 execute DATABASE --file=<tmp.sql> [--local|--remote]` with a single batched file of `INSERT OR REPLACE` statements per period; reads use `wrangler d1 execute DATABASE --command "<SELECT …>" --json [--local|--remote]` and parse the JSON result. Wrap this in one module, `scripts/common/d1.py`, with a `target` of `local` (default) or `remote`.
- **Rationale**: This is the path the repo already trusts — `import-to-d1.mjs` runs `wrangler d1 execute --file`, and `db:migrate:dev/prod` run `wrangler d1 migrations apply --local/--remote`. `--json` is supported for result sets. It needs no new dependency and works identically for local Miniflare state and remote production. Verified flags: `--command`, `--file`, `--local`, `--remote`, `--json`.
- **Alternatives considered**:
  - *Cloudflare D1 HTTP/REST API directly from Python (`requests`/`httpx`)* — rejected: there is no D1 public REST surface used here, and no `CLOUDFLARE_API_TOKEN`/`account_id` exists in the repo; it would add a dependency and a new credential/trust path.
  - *Write the local Miniflare SQLite file directly with Python's `sqlite3`* — rejected: brittle (internal Miniflare path, WAL, metadata DBs, schema-version coupling) and cannot reach remote at all, so analysis/scrape would need two code paths.

## SQL generation (port from `import-to-d1.mjs`)

- **Decision**: Port the existing JS SQL generation into `scripts/common/d1.py`: derive column names from each row dict, emit `INSERT OR REPLACE INTO "<table>" (...) VALUES (...)`, escape values the same way (`NULL`/number/`0|1`/JSON-stringified object/single-quote-escaped string), keep `TABLE_ORDER`, prepend `PRAGMA defer_foreign_keys = ON;`, and flatten nested `document_analyses.analysis_records` into `document_analysis_records`.
- **Rationale**: Behavioral parity with today's import is the success criterion (SC-002). Re-implementing the same, already-correct logic in Python — rather than inventing new serialization — guarantees identical rows and keeps the column set driven by the data (no hand-maintained column lists that could drift from the Drizzle schema).
- **Alternatives considered**: *Keep `import-to-d1.mjs` and have Python shell out to it* — rejected: it depends on a JSON file we are eliminating, and FR-014 requires removing the file-based path. *An ORM/query-builder in Python* — rejected: new dependency, no benefit over deterministic string SQL for bulk upsert.

## Atomicity / partial-write safety (FR-007, SC-006)

- **Decision**: Build the whole period's upsert as one SQL file and execute it in a single `wrangler d1 execute --file` call; on any error, report failure and stop. Correctness on retry is guaranteed by `INSERT OR REPLACE` keyed on the deterministic IDs — re-running a period fully overwrites it.
- **Rationale**: A single batched execution is what `import-to-d1.mjs` already does, and idempotent upsert means a failed or partial run is *healed* by re-running, so the database is never left in a divergent state that a re-scrape can't fix. This satisfies the spec's "either fully lands or is cleanly reported, prior state preserved" intent without depending on a cross-statement transaction guarantee that D1's batch model does not strongly promise across chunked remote execution.
- **Alternatives considered**: *Explicit `BEGIN/COMMIT` wrapping* — kept as a best-effort addition where supported, but not relied upon for correctness because remote execution may chunk; idempotent upsert is the actual safety net. *Per-table separate executions* — rejected: more failure points, weaker atomicity.

## Page images: vision needs a local file even though storage is R2

- **Decision**: The scraper uploads each page image to R2 during the run (no disk resting place for the source of truth). For analysis, a small `scripts/analysis/images.py` **materializes** the in-scope page bytes from R2 into an ephemeral, git-ignored cache directory; `classify-doc-page` (vision) and `nf_groups.content_hash` read those cache files; the cache is scratch, never authoritative.
- **Rationale**: Claude vision via the Read tool requires a real local file path, and NF grouping hashes raw page bytes — neither can operate on an R2 key directly. Materializing on demand keeps "the source of truth is R2, nothing rests in the data folder" true while giving the vision/grouping steps the local files they need. The operator explicitly allowed transient working artifacts to remain local scratch.
- **Alternatives considered**: *Persist images to disk during scrape too (dual-write)* — rejected: contradicts the operator's "no page image rests in the data folder." *Store a content-hash column on `documents` at scrape time to avoid re-hashing* — rejected: that is a D1 schema change (new column → Drizzle migration), and the plan commits to an unchanged schema; hashing the materialized bytes at analysis time preserves current behavior with zero schema impact.

## `documents.file_path` ↔ R2 object-key contract

- **Decision**: The scraper writes `documents.file_path` as the `;`-joined list of **R2-key-form** tokens `<period>/<basename>` (e.g. `2025-12/<entry_id>_p1.png`), which is exactly the key it uploads to. `src/lib/r2.ts:objectKeyFromFilePath()` already returns such a token unchanged (no `data/scrape/` marker to strip), so the frontend resolves images with no change, and analysis materialization uses the same token as the R2 key.
- **Rationale**: Keeps a single, round-trippable key between writer (scraper), reader (frontend), and materializer (analysis), and stays backward-compatible with legacy rows that stored the `…/data/scrape/<period>/<basename>` form (still handled by `objectKeyFromFilePath`).
- **Alternatives considered**: *Keep storing the old disk-path form* — rejected: misleading once nothing lives on disk; the R2-key form is the truth and is what every consumer needs.

## Local vs. remote selection convention

- **Decision**: A `--remote` boolean flag on the `scrape` and analysis commands selects remote; absence means local. Mirrors `import-to-d1.mjs` and the `db:migrate:dev/prod` split. The CLI prints the resolved target before any write; the `improve-classification` loop and the agents thread the same flag through.
- **Rationale**: Matches the only convention the project already uses for local/remote; least surprise; a safe local default prevents accidental production writes (FR-004, SC-003). Remote relies on the operator's existing `wrangler` auth.
- **Alternatives considered**: *An environment variable (e.g. `TARGET=remote`)* — rejected: the repo nowhere uses an env var for this; per-invocation explicitness is safer for a tool that can write production.

## Ephemeral analysis cache location

- **Decision**: Materialized images and per-run scratch (`.classify.json`, `<period>.extract-todo.json`, `<period>.verdicts.json`) live under a dedicated, git-ignored cache directory keyed by period (`.cache/analysis/<period>/`), located **outside the `data/` tree entirely**. A `--cache-dir` option (defaulting there) lets a run override it.
- **Rationale**: The operator asked to "skip saving data into the data folder," so the cache is deliberately placed outside `data/` (not under `data/.cache/`) to avoid any ambiguity. It is not a source of truth and is fully reproducible from D1+R2, while still giving the file-oriented scratch steps a stable home across a multi-step loop iteration.
- **Alternatives considered**: *`data/.cache/`* — rejected: although gitignored and non-authoritative, it sits literally inside the data folder the operator wants emptied, which is confusing. *System `/tmp`* — viable but harder to inspect when debugging a loop; a repo-local git-ignored cache is friendlier. *Reuse `data/scrape/`* — rejected: blurs the "data folder is gone" boundary and risks stale authoritative-looking files.

## Scratch files vs. SQL (operator's question: "do we need scratch files if we are using sql?")

- **Decision**: Where D1 supersedes a file, eliminate it: the period JSON and the `document_analyses`/`alerts` writeback move fully into D1. The remaining scratch (`.classify.json`, `.extract-todo.json`, `.verdicts.json`) stays as ephemeral local files **for now**, because (a) `classify-doc-page` is a vision skill whose natural output is a sibling file next to the image it Read, and persisting raw per-page vision output to D1 would require a new scratch table (schema change) for marginal benefit; (b) the manifest and verdicts are loop-iteration bookkeeping that is cheaply regenerated and intentionally not part of the persisted dataset. They are no longer the data hand-off *into* the database — only intra-run coordination.
- **Rationale**: Directly implements the operator's answer ("if we still need them, local scratch is fine for now") and Principle V (no new schema/abstraction without concrete present need).
- **Alternatives considered**: *A `page_classifications` D1 scratch table* — deferred: adds a migration and a remote-write of throwaway data; revisit only if cross-machine loop resumption becomes a requirement.

## No new dependencies

- **Decision**: Add no npm or pip packages. Python uses stdlib (`subprocess`, `json`, `tempfile`, `hashlib`, `pathlib`) plus the existing `playwright` for downloads; `wrangler` is already present.
- **Rationale**: Constitution Principle V and the spec's no-new-dependency posture from adjacent features (012/013).
