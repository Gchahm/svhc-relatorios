# Research: TypeScript test harness — decisions

## D1. Harness: minimal `node:test` vs. DOM component-test stack

- **Decision**: Use the existing **`node:test` + native TS type-stripping** path; add **no** DOM
  / component-test dependency. Logic inside `"use client"` `.tsx` components is extracted into
  sibling pure `.ts` modules and tested there.
- **Rationale**:
  - The repo's no-new-deps culture and the parallel Python testing track (TEST-002, stdlib
    `unittest` + `coverage`) set a strong precedent for zero/minimal tooling.
  - All five user stories reduce to **pure** functions: metadata parsing, URL building, status
    math + label mapping, an auth allow/deny decision, row→response shaping, and a deep-link →
    view-state decision. None requires a real DOM or React render to be *meaningfully* asserted —
    asserting behavior (not markup) is exactly what the spec mandates (FR-010).
  - `@testing-library/react` + a DOM (jsdom/happy-dom) + a runner (`vitest`) would add 3+ heavy
    dev dependencies and a second test runner/config, for rendering coverage the spec explicitly
    deprioritizes ("no snapshot sprawl; assert behavior, not markup").
- **Alternatives considered**:
  - *vitest + RTL + jsdom*: rejected — new deps + second runner; only justified if a flow can't be
    pinned without a DOM, which is not the case here (the deep-link view-state is a pure decision).
  - *Leave `.tsx` logic inline and skip it*: rejected — leaves the highest-risk flow untested.

## D2. `.tsx` cannot be imported by `node:test` (empirically confirmed)

- **Finding**: Node 22.22.3 strips types from **`.ts`** (the existing tests import `./alerts.ts`,
  `./documents.ts`, `./deepLink.ts`) but raises `ERR_UNKNOWN_FILE_EXTENSION` for **`.tsx`**.
  Importing `src/app/dashboard/alerts/alerts.tsx` (a `"use client"` file importing React/Badge)
  from a `.test.mjs` fails on the extension before any React concern.
- **Decision**: Extract the pure helpers out of each `.tsx` into a sibling `.ts` module
  (`alerts-helpers.ts`, `deeplinkView.ts`, `i18n/alert-type-label.ts`); the `.tsx` imports/re-exports
  them so its public surface and runtime behavior are unchanged.
- **Rationale**: This is the established repo pattern (`deepLink.ts` is exactly such an extraction,
  already imported by `deepLink.test.mjs`). It keeps tests stdlib-only and per-file coverage clean.

## D3. Coverage reporting + baseline/ratchet without a new dependency

- **Decision**: Use Node's built-in `node --test --experimental-test-coverage` with
  `--test-coverage-exclude='**/*.test.mjs'` (drop test files from the report) and the threshold
  flags `--test-coverage-lines/branches/functions=<baseline>` as the ratchet. The recorded
  baseline lives as the threshold numbers in the `test:ts:cov` package script (mirroring how the
  Python side records its baseline). Raising coverage never fails; dropping below the baseline
  exits nonzero.
- **Verification**: at the threshold → exit 0; one point above current → exit 1 (confirmed). Test
  files are excluded; only imported source modules appear in the report.
- **Rationale**: Zero new dependency; the runner is already `node --test`. Matches the spec's
  Assumptions and the TEST-002 policy intent (recorded baseline + enforced ratchet).
- **Alternatives considered**: `c8` / `nyc` — rejected (new dep, redundant with built-in V8
  coverage). A bespoke baseline-diff script parsing the report — rejected as unnecessary since the
  native threshold flags already gate.
- **Note on baseline scope**: Node's V8 coverage only attributes files that are **loaded** by the
  test run. The baseline is therefore the coverage of the **tested module set**; the ratchet
  guarantees that set's coverage never regresses. New untested `src/` files do not silently lower
  the number (they're simply absent), which is the same property the Python per-run coverage has;
  the ratchet's job is regression-prevention on covered code, consistent with TEST-002.

## D4. Auth status code (401 vs 403)

- **Decision**: The routes currently return **403** for an unauthorized session. Tests pin the
  allow/deny **decision** and import the `UNAUTHORIZED_STATUS` **constant from the extracted auth
  module**, asserting the route uses that same constant — rather than independently hardcoding 401
  or 403 in the test. The test stays correct if the team later changes the code.
- **Rationale**: Avoids a brittle, duplicated magic number; pins the security-relevant behavior
  (deny by default) rather than an incidental code.

## D5. Expected-label source of truth

- **Decision**: All UI-string assertions resolve their expected value from `catalog["pt-BR"]`
  (e.g. `catalog["pt-BR"].status.over` === "Acima", `catalog["pt-BR"].alert.types.<type>`),
  never a hardcoded English literal (FR-009). `catalog.ts` is pure data and imports cleanly under
  `node:test` (verified).
- **Rationale**: The dashboard is localized pt-BR (#72–#75); the catalog is the single source of
  truth, so an assertion against it cannot drift from what the UI renders.

## D6. Scope of API-handler extraction

- **Decision**: Extract and test the shared `isAuthorized` decision + the row→response shaping for
  the three named surfaces (`/api/alerts`, `/api/documents`, `/api/attachment-analyses`). Other
  routes (detail routes, image streaming, auth catch-all) are **out of scope** for this issue.
- **Rationale**: Matches the issue's enumerated targets; keeps the change focused and reviewable.
