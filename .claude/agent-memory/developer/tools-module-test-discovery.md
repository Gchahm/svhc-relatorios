---
name: tools-module-test-discovery
description: How to run/import a self-contained Python module under tools/ (e.g. doc_transcribe) and its unittest suite
metadata:
  type: project
---

The `tools/` dir holds self-contained Python tooling modules that must NOT import from `scripts/analysis` (e.g. `tools/doc_transcribe/`, the EXTRACT typed-schema contract). These are stdlib-only and importable as a package.

**Why:** the design (`docs/features/false-positive-triage-agent.md` §11.6) keeps the reusable transcriber/schema layer extractable to its own repo — so it gets its own dir under `tools/`, not under `scripts/`.

**How to apply:**
- Use an **underscore** dir name (`tools/doc_transcribe/`, not `doc-transcribe`) so it is a valid importable package. The design doc's hyphen spelling is the same module.
- Run its unittest suite with `tools` as the top-level so the package imports resolve:
  `uv run python -m unittest discover -s tools/doc_transcribe/tests -t tools`
  Tests then import `from doc_transcribe import ...` and shared helpers via the package path `from doc_transcribe.tests._helpers import ...` (a bare `from _helpers import` fails because the tests dir is not on sys.path when top-level is `tools`).
- CI's `pnpm test:py` discovers ONLY `scripts/tests`; a new `tools/` module's tests are a separate invocation and are not in CI by default (wiring them in is a follow-up, not required by the contract issue).
- `prettier --check .` (CI `pnpm format:check`) DOES cover `tools/` — `.prettierignore` excludes `.claude`/`specs`/`drizzle` but not `tools/`. Run `prettier --write 'tools/**/*.{json,md}'` before committing or CI format gate fails.
