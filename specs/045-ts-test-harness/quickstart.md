# Quickstart: TypeScript test harness

## Run the tests

```bash
pnpm test:ts        # run every TypeScript test (node --test over src/**/*.test.mjs)
pnpm test:ts:cov    # same, with src/ coverage report + baseline ratchet (fails below baseline)
pnpm test           # test:ts + test:py (both suites)
```

CI runs `pnpm test:ts` (TypeScript tests step) and `pnpm test:ts:cov` (TypeScript coverage step)
in `.github/workflows/ci.yml`.

## How it works (no new dependency)

- Node 22 strips TypeScript types from `.ts` natively, so `*.test.mjs` files import the **real**
  `.ts` modules (never a re-derived copy). `.tsx` cannot be imported by `node:test`, so pure logic
  is extracted into sibling `.ts` modules that the `.tsx` components import.
- Coverage uses Node's built-in `--experimental-test-coverage`; the ratchet is the
  `--test-coverage-lines/branches/functions=<baseline>` flags, with `--test-coverage-exclude`
  dropping the `*.test.mjs` files from the report.

## Add a test

1. Put the pure logic in a `.ts` module (extract it out of a `.tsx` component if needed).
2. Add a colocated `<name>.test.mjs` importing the real `.ts` module:
   ```js
   import test from "node:test";
   import assert from "node:assert/strict";
   import { thing } from "./thing.ts";
   ```
3. Assert UI-string expectations against the catalog, never an English literal:
   ```js
   import { catalog } from "@/lib/i18n/catalog"; // or a relative path
   assert.equal(label, catalog["pt-BR"].status.over);
   ```
4. Run `pnpm test:ts`. If you covered more code, you may raise the `test:ts:cov` baseline (never
   lower it without justification).

## Updating the coverage baseline

The baseline lives as the threshold numbers in the `test:ts:cov` script in `package.json`. The
recorded baseline is **90%** lines/branches/functions — set a few points below the measured 100%
of the tested module set (the same small-margin policy as the Python `fail_under = 78`: a real
regression fails CI, trivial non-functional churn does not). Raise it when new tests durably
increase coverage; lowering it is a regression and must be justified in review.
