# Phase 0 Research: Shared reconciliation tolerance/status contract

## R1 — How does the TS test import the real `documentStatus` with no new dependency?

**Decision**: Use Node.js's built-in test runner (`node --test`) and import
`src/lib/documents.ts` directly; Node ≥22.18 strips TypeScript types natively (no
`--experimental-strip-types` flag needed on v22.22.3, the container's version).

**Evidence**: A smoke test (`import { documentStatus } from ".../src/lib/documents.ts"`)
under `node --test` passed on v22.22.3, exercising the actual exported function. Only a
benign `MODULE_TYPELESS_PACKAGE_JSON` warning is emitted (Node reparses as ESM because
module syntax is detected) — the test still runs and passes.

**Rationale**: Importing the real function (not a copy) is the whole point — the test must
fail when the production logic changes. `documents.ts` is pure (no React, no Cloudflare
binding, no other import), so it loads in plain Node with nothing mocked. Zero new npm
dependency (FR-008), satisfies A3's "import, never re-derive".

**Alternatives considered**:
- *Vitest / Jest*: rejected — adds an npm dependency, violates the no-new-dep convention.
- *Compile `documents.ts` to JS first*: rejected — adds a build step; native type-stripping
  removes the need.
- *Re-implement the math in the test*: rejected — defeats the purpose (the test would drift
  with neither source file).

## R2 — How is the TS test discovered/run?

**Decision**: Name the file `src/lib/documents.test.mjs` and run it via an explicit glob:
`node --test "src/**/*.test.mjs"`. Wire this as the `test` script in `package.json`
(extended to also run the Python suite — see R5).

**Evidence**: `node --test "<dir>/**/*.test.mjs"` (glob) reliably discovers and passes the
file; passing a bare **directory** to `node --test` produced a spurious top-level failure on
this Node version, so the explicit glob is used instead.

**Rationale**: `.mjs` forces ESM unambiguously and avoids the `package.json` `type` question
(the repo's `package.json` has no `"type"`, defaulting to CommonJS, but `.mjs` overrides
that per-file). Co-locating the test with `documents.ts` keeps the contract visible next to
the code it guards.

**Alternatives considered**:
- *`node --test src/`* (bare dir): rejected — spurious failure on this Node version (above).
- *Add `"type": "module"` to package.json*: rejected — broad, risky change to a Next.js
  app; `.mjs` is local and sufficient.

## R3 — Where does the shared fixture live, and in what format?

**Decision**: `scripts/analysis/reconciliation_contract.json`, a JSON object with a `cases`
array of `{ "name", "sum", "total", "status" }` records; `total` may be `null`; `status` is
one of `within` | `over` | `under` | `unknown`. A top-level `notes` field documents the
canonical-name mapping for human readers.

**Rationale**: JSON is read natively by both `json.load` (Python) and `JSON.parse`/`import`
(Node). Placing it under `scripts/analysis/` (a) sits next to the canonical Python
implementation, (b) keeps it out of the Next.js build graph (it is test data, never imported
by app code), and (c) is reachable by both tests via short relative paths:
`scripts/tests/` → `../analysis/reconciliation_contract.json`; `src/lib/` →
`../../scripts/analysis/reconciliation_contract.json`.

**Alternatives considered**:
- *Fixture under `src/`*: rejected — would pull test data into the app's module graph /
  type-check scope.
- *Fixture under `specs/`*: rejected — specs are documentation, not a runtime contract the
  shipped tests load.
- *Duplicate fixture per language*: rejected — defeats "single source of truth" (SC-001).

## R4 — What are the canonical cases and the status-name mapping?

**Decision**: Canonical status vocabulary is the TS one (`within`/`over`/`under`/`unknown`).
The Python test maps `reconcile_group` output through:
`{"reconciled": "within", "over_claim": "over", "under_claim": "under", None: "unknown"}`.

Minimum cases (FR-002), with the band = (abs `<= 0.05`) OR (rel `< 0.05`):

| name                    | sum     | total   | diff  | rel    | status   | why |
|-------------------------|---------|---------|-------|--------|----------|-----|
| exact_match             | 100.00  | 100.00  | 0     | 0      | within   | exact |
| abs_band_inclusive      | 100.05  | 100.00  | 0.05  | 5e-4   | within   | abs `<=` includes 0.05 |
| abs_band_just_over_only_rel | 10400.00 | 10000.00 | 400 | 0.04 | within | over abs band, inside rel band |
| rel_band_exact_excluded | 10500.00 | 10000.00 | 500   | 0.05   | over     | rel is strict `<`, exactly 5% excluded |
| clear_over              | 200.00  | 100.00  | 100   | 1.0    | over     | outside both |
| clear_under             | 50.00   | 100.00  | 50    | 0.5    | under    | outside both, sum<total |
| just_over_abs_small     | 100.06  | 100.00  | 0.06  | 6e-4   | over     | small total: 0.06 > abs, 6e-4 < rel? 6e-4<0.05 → within! (see note) |
| null_total              | 100.00  | null    | —     | —      | unknown  | no total |
| zero_total              | 100.00  | 0.00    | —     | —      | unknown  | total <= 0 |
| negative_total          | 100.00  | -5.00   | —     | —      | unknown  | total <= 0 |

**Note / correction**: For a *small* total like 100, the relative band (5% = R$5.00)
dominates, so `100.06` is `within` (diff 0.06 ≪ rel 5.00). To get a genuine "just over for a
small total" the case must escape **both** bands — e.g. `sum=110, total=100` (diff 10 > abs
0.05 AND rel 0.10 ≥ 0.05) → `over`. The fixture uses `clear_over`/`clear_under` (200/100,
50/100) for the unambiguous over/under and the two large-total cases
(`abs_band_just_over_only_rel`, `rel_band_exact_excluded`) to lock the abs-inclusive /
rel-strict asymmetry. The misleading `just_over_abs_small` row above is **dropped** from the
final fixture to avoid encoding a wrong expectation.

**Rationale**: These cases pin every branch of both implementations: the abs `<=` inclusive
boundary, the rel `<` strict boundary, both over/under sides, and all three "unknown"
triggers (null, zero, negative). A unilateral change to any constant or comparison operator
flips at least one case (FR-006).

## R5 — How to satisfy "fail CI" without touching CI wiring?

**Decision**: Add a `package.json` `test` script that runs **both** suites:
`node --test "src/**/*.test.mjs" && python -m unittest discover -s scripts/tests -t scripts`.
Document the two commands in quickstart.md. The repo's CI config is out of scope (A4); a
runnable, dependency-free `pnpm test` that fails on drift satisfies the intent.

**Rationale**: One command runs the whole contract guard. If a CI step later calls
`pnpm test`, drift fails the build automatically.

**Alternatives considered**:
- *Add a GitHub Actions workflow*: deferred — CI wiring is explicitly out of scope (A4) and
  the repo has no existing test workflow to extend.
