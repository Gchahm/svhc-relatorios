# Implementation Plan: Shared reconciliation tolerance/status contract

**Branch**: `036-shared-tolerance-contract` | **Date**: 2026-06-12 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/036-shared-tolerance-contract/spec.md`

## Summary

Bind the two independent reconciliation over/within/under implementations
(`scripts/analysis/nf_groups.py` `within_tolerance`/`reconcile_group`, and
`src/lib/documents.ts` `documentStatus`) to one canonical contract so neither can silently
drift. Approach (issue Suggestion 2): one language-neutral JSON fixture of `(sum, total) →
status` cases, plus two thin contract tests — a Python `unittest` and a Node.js built-in
`node --test` — each loading the **same** fixture and asserting the **real** exported
function matches it. Both tests import the actual production logic (no re-derivation). Add a
cross-reference comment to each source file and a dependency-free `pnpm test` script. No
behavior, schema, or dependency change.

## Technical Context

**Language/Version**: Python 3.12 (analysis under `scripts/`, run via `uv`); TypeScript 5 / Node.js 22 (the app + test runner)
**Primary Dependencies**: None added. Python stdlib `unittest`/`json`; Node.js built-in `node:test`/`node:assert`; native TS type-stripping in Node 22.18+ (confirmed v22.22.3) to import `documents.ts` with no bundler.
**Storage**: N/A — no D1/R2 access, no schema, no migration.
**Testing**: `python -m unittest discover -s scripts/tests -t scripts` (existing) + `node --test` over a new `*.test.mjs` (new, dependency-free); wired into a `pnpm test` script.
**Target Platform**: CI / developer workstation (Linux).
**Project Type**: Web app (Next.js) + Python analysis pipeline — a cross-language guard spanning both.
**Performance Goals**: N/A (tests run in <1s).
**Constraints**: No new npm or pip dependency (constitution Principle V / repo convention). No production behavior change (FR-010). Tests must currently pass and must fail on unilateral drift (FR-005/FR-006).
**Scale/Scope**: ~1 fixture file, 2 test files, 2 one-line source comments, 1 package.json script. ~10 contract cases.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- **I. Type Safety & Schema Discipline**: PASS. No schema change, no migration, no
  `auth.schema.ts` edit. The TS test imports the typed `documentStatus`; type-stripping does
  not weaken types in production code (it only runs the test). No `any`.
- **II. Cloudflare-Native Architecture**: PASS / N/A. No DB access — the tested function is
  a pure helper; the test never touches `getDb()` or bindings.
- **III. Quality Gates Before Commit**: PASS. Run `pnpm lint` + `pnpm format` before commit;
  this feature *adds* a quality gate (the contract tests) rather than bypassing one.
- **IV. Security & Auth by Default**: PASS / N/A. No routes, no auth surface, no data
  exposure — pure logic + a fixture.
- **V. Simplicity & Incremental Delivery**: PASS. Smallest correct guard (the issue's
  recommended option); rejects the larger persist-status restructure (A5). Zero new deps.

No violations → Complexity Tracking left empty.

## Project Structure

### Documentation (this feature)

```text
specs/036-shared-tolerance-contract/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/           # Phase 1 output (fixture schema + cases doc)
└── tasks.md             # Phase 2 output (speckit tasks)
```

### Source Code (repository root)

```text
scripts/
└── analysis/
    └── reconciliation_contract.json   # NEW — canonical shared fixture (the single source of truth)
scripts/analysis/nf_groups.py          # EDIT — add cross-reference comment (FR-007)
scripts/tests/
└── test_reconciliation_contract.py    # NEW — Python contract test, loads the fixture

src/lib/documents.ts                   # EDIT — add cross-reference comment (FR-007)
src/lib/documents.test.mjs             # NEW — Node --test contract test, loads the same fixture + imports documentStatus

package.json                           # EDIT — add a dependency-free `test` script
```

**Structure Decision**: The fixture lives at `scripts/analysis/reconciliation_contract.json`
— next to the canonical Python implementation (`nf_groups.py`), reachable by the Python test
in `scripts/tests/` via a relative path and by the TS test via a relative path from
`src/lib/`. Placing it under `scripts/analysis/` (not `src/`) keeps it out of the Next.js
build graph (it is test-only data, never imported by app code) while staying a single file
both languages read. Tests sit beside their existing suites: Python in `scripts/tests/`
(picked up by the existing `unittest discover`), TS co-located with `documents.ts` as
`documents.test.mjs` (matched by `node --test`'s default `*.test.mjs` glob).

## Complexity Tracking

> No constitution violations — no entries required.
