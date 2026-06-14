---
name: node-test-import-resolution
description: Pure .ts modules tested with node --test must use RELATIVE imports with explicit .ts extensions, and only import other modules whose own imports are likewise resolvable (type-only or .ts-extension)
metadata:
  type: feedback
---

A `.ts` module that you want unit-tested via the repo's `pnpm test:ts` (`node --test "src/**/*.test.mjs"`, which strips types and runs `.ts` directly) MUST:

1. Import siblings with **relative paths AND explicit `.ts` extensions** (e.g. `import { x } from "../../../lib/i18n/catalog.ts"`). The `@/*` path alias is a tsconfig/bundler feature — `node --test` does NOT resolve it → `ERR_MODULE_NOT_FOUND: Cannot find package '@/lib'`. (`allowImportingTsExtensions: true` is already set in tsconfig, so `.ts` extensions also build fine under Next — `deeplinkView.ts`/`deepLink.ts` already do this.)
2. Only import modules whose OWN imports are node-resolvable. A transitive import that uses an **extension-less relative import** (e.g. `formatters.client.ts` does `from "./formatters.core"` with no `.ts`) will also fail under node:test. Pick the leaf that's clean: e.g. import `formatCurrencyFor` from `formatters.core.ts` (its only import is `import type … from "./catalog"`, a type-only import node strips) instead of `formatCurrency` from `formatters.client.ts`.

**Why:** Building a UI helper as a pure, dependency-light `.ts` module + a `.test.mjs` (the established `deeplinkView` pattern) is how repo TS logic gets unit-tested without a React renderer. Getting the import style wrong makes the whole test file fail to load (counts as 1 failing test, not a clear error).

**How to apply:** When extracting renderer/decision logic into a testable `.ts` for `node:test`, default to relative `.ts`-extension imports and trace the import chain to confirm every hop is type-only or `.ts`-extensioned before relying on the test. Also see [[tools-module-test-discovery]] for the Python side.
