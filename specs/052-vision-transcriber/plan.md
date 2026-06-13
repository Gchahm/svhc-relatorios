# Implementation Plan: Standalone vision transcriber module (image → typed JSON)

**Branch**: `052-vision-transcriber` | **Date**: 2026-06-13 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/052-vision-transcriber/spec.md`

## Summary

Add `transcribe(image, doc_type="auto", *, backend="cli", model=...) → {doc_type, schema_version,
fields, parse_errors?}` plus an equivalent CLI to the existing self-contained `tools/doc_transcribe/`
module (the EXTRACT-001 schema registry + validator). The function resolves the document type through
the registry, asks a **pluggable backend** to transcribe the page image into that type's JSON Schema,
then validates the returned JSON **above the backend** against the EXTRACT-001 schema (`validate_transcription`)
and returns the typed result — recording any validation failures in `parse_errors` instead of raising.
Two backends behind one tiny interface: `cli` (default — shells out to `claude -p`, no `anthropic` SDK,
no `ANTHROPIC_API_KEY`, runs in its own subprocess) and `api` (Anthropic Messages API via the optional
`anthropic` SDK with `output_config.format` json_schema, requires `ANTHROPIC_API_KEY`). The module stays
stdlib-only on the default path, imports without `anthropic`, never imports `scripts/analysis`, and adds
no mandatory dependency. The pure surface is unit-tested with stdlib `unittest` and an injected fake
backend (no subprocess, no network).

## Technical Context

**Language/Version**: Python 3.12 (the `tools/doc_transcribe/` package; run via `uv`). Stdlib-only on
the default path; `anthropic` SDK is an optional extra used only by the `api` backend.
**Primary Dependencies**: Existing only — `tools/doc_transcribe` registry (`schema_for`, `canonical_type`,
`SCHEMA_VERSION`, `DOC_TYPES`) + validator (`validate_transcription`). Stdlib `subprocess`/`json`/`base64`/
`argparse`/`pathlib`/`importlib`. The `cli` backend needs the `claude` binary on PATH (runtime, not a
Python dep). The `api` backend lazily imports `anthropic` (optional extra).
**Storage**: N/A — no D1/R2, no DB schema, no migration. Reads an image file from disk; writes nothing.
**Testing**: stdlib `unittest` under `tools/doc_transcribe/tests/`, run with
`uv run python -m unittest discover -s tools/doc_transcribe/tests -t tools`. Backend is injected/stubbed
(a fake `Backend` returning canned JSON); no real `claude` subprocess, no Anthropic API, no network.
**Target Platform**: Local dev / CI shell (the analysis toolchain). Not the Workers runtime.
**Project Type**: Single self-contained tooling module under `tools/` (mirrors EXTRACT-001 placement).
**Performance Goals**: N/A (latency is dominated by the external model call; not in scope to optimize).
**Constraints**: Zero imports of `scripts/analysis`; module imports with `anthropic` absent; no new
mandatory pip/npm dependency; `cli` backend touches no API key; transcribe-only (no reconciliation
math). `prettier --check .` covers `tools/` markdown/json — run `prettier --write` before commit.
**Scale/Scope**: One module file (`transcribe.py`) + backend seam + CLI entry (`__main__.py`) + tests;
~5 new functions/classes. No change to the EXTRACT-001 schemas/registry/validator.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- **I. Type Safety & Schema Discipline** — PASS. No TypeScript, no Drizzle/auth schema. The typed
  contract is the EXTRACT-001 JSON Schema, reused unchanged; validation is `validate_transcription`.
  Python type hints throughout (mirrors the module's existing `from __future__ import annotations`).
- **II. Cloudflare-Native Architecture** — N/A. No D1/R2/Workers binding; this is an offline analysis
  tool. No `getDb()`/`getCloudflareContext()` involved.
- **III. Quality Gates Before Commit** — PASS. `pnpm lint`/`pnpm format` (prettier covers `tools/`).
  Tests are explicitly requested by the spec (FR-012) and follow the repo's stdlib `unittest`
  convention; they MUST pass before merge.
- **IV. Security & Auth by Default** — PASS. No new route, no user/fiscal data exposure. Secrets:
  `ANTHROPIC_API_KEY` is read from the environment by the `api` backend only, never committed, never
  required by the default path — consistent with "secrets in env, never in source".
- **V. Simplicity & Incremental Delivery** — PASS. One small module extending an existing one; one
  thin backend interface with two implementations; the `anthropic` SDK is optional (no mandatory new
  dependency). P1 (cli + library) is independently shippable; P2 (api, CLI) layers on top.

No violations → Complexity Tracking left empty.

## Project Structure

### Documentation (this feature)

```text
specs/052-vision-transcriber/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/           # Phase 1 output (transcribe.md — the function/CLI/backend contract)
├── checklists/
│   └── requirements.md  # specify-phase quality checklist
└── tasks.md             # Phase 2 output (speckit tasks)
```

### Source Code (repository root)

```text
tools/doc_transcribe/
├── __init__.py              # CHANGED: re-export transcribe + TranscriptionResult + Backend types
├── registry.py              # UNCHANGED (EXTRACT-001)
├── validator.py             # UNCHANGED (EXTRACT-001)
├── transcribe.py            # NEW: transcribe(), result assembly, type resolution, parse-error capture
├── backends.py              # NEW: Backend protocol + CliBackend (claude -p) + ApiBackend (anthropic SDK)
├── prompts.py               # NEW: build the per-type transcription instruction (shared by both backends)
├── __main__.py              # NEW: CLI — `python -m doc_transcribe --image <path> [--type] [--backend]`
├── schemas/<type>.json      # UNCHANGED (EXTRACT-001)
├── examples/<type>.json     # UNCHANGED (EXTRACT-001)
└── tests/
    ├── _helpers.py          # CHANGED (if needed): a FakeBackend + sample-image helper
    ├── test_transcribe.py   # NEW: result assembly, type resolution, parse-error capture, raw_text floor
    ├── test_backends.py     # NEW: cli arg/JSON-extraction + api request assembly (both stubbed), optional-dep errors
    └── test_cli.py          # NEW: CLI prints typed JSON / errors+exit codes (backend injected)
```

**Structure Decision**: Extend the existing self-contained `tools/doc_transcribe/` package (the
EXTRACT-001 contract lives here; EXTRACT-002 is the transcriber on top of it, per design §11.6). New
files only — the registry/validator/schemas are untouched. Underscore dir name keeps it importable;
tests run with `-t tools` as established (memory: `tools-module-test-discovery`).

## Complexity Tracking

> No constitution violations — table intentionally empty.
