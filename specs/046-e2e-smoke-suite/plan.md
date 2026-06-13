# Implementation Plan: Integration/E2E Smoke Suite — Seeded Local D1/R2 + Browser Flows

**Branch**: `046-e2e-smoke-suite` | **Date**: 2026-06-13 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/046-e2e-smoke-suite/spec.md`

## Summary

Add an integration + end-to-end smoke test layer that runs against a real local Miniflare D1/R2 and the real Workers build — the seams the unit suites only stub. Three pieces: (1) a deterministic, idempotent, **synthetic-only** seed (`scripts/e2e/seed.py`) that applies migrations and populates one far-future period (`2099-01`) across D1 + R2; (2) Python **integration tests** (`scripts/integration_tests/`) that drive the real `scripts/common/d1.py` writebacks (`_merge_and_write`, `mark-pending`, `build-documents`, feature-028 reconciliation) and assert post-state by reading D1 back, each verified idempotent; (3) a **browser E2E smoke** using the Python Playwright `sync_api` (already in the toolchain — no new JS dep) against `pnpm preview`, covering sign-in + auth gate, entries render, alert deep link → analysis dialog (+ feature-037 not-found notice), documents statuses, and the auth-gated image route. Wired into CI as a **separate `e2e` job** parallel to `verify`.

## Technical Context

**Language/Version**: Python 3.12 (seed + integration + browser smoke, via `uv`); TypeScript 5 / Node 22 only as the build target served by `pnpm preview`.
**Primary Dependencies**: Existing only — `scripts/common/d1.py` (`wrangler`-CLI wrapper), `scripts/common` (`det_id`, `now_ms`), Python `playwright` (`sync_api`, already a scraper dep, Chromium installed at `/opt/playwright/...`), `wrangler` (D1 migrations + R2), `@opennextjs/cloudflare` (`pnpm preview`). **No new npm or pip dependency** (`@playwright/test` deliberately not added — FR-008).
**Storage**: Cloudflare D1 (`DATABASE` → `fiscal-db`) + R2 (`DOCUMENTS` → `fiscal-documents`), **local Miniflare only** (`--local`). Seed writes mirror + analysis-owned + auth tables; tests read/write via the real wrapper. No `--remote`, no production secret.
**Testing**: Python stdlib `unittest` for the integration tests (matches the existing `scripts/tests` convention), discovered from a **separate** path (`scripts/integration_tests/`) so `pnpm test:py` (unit) never touches Miniflare. The browser smoke is a standalone `unittest`-style runner invoked through `uv run`.
**Target Platform**: Linux (dev container + GitHub Actions `ubuntu-latest`).
**Project Type**: Web app (Next.js 15 on Cloudflare Workers) — this feature adds a test layer only, no app code.
**Performance Goals**: Seed < 2 min (SC-001); whole `e2e` CI job target ≤ ~10 min so it can stay PR-gating (FR-010).
**Constraints**: Synthetic data only, no real ledger artifacts (FR-002); no D1 schema change / migration; no app-code change; bounded waits (no hangs, FR-012); idempotent seed + idempotent writebacks (FR-003, FR-005).
**Scale/Scope**: One synthetic period, ~6 entries, ~5 attachments, ~3 documents, ~3 alerts; ~4 integration tests; ~6 browser smoke checks.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- **I. Type Safety & Schema Discipline** — PASS. No schema change, no migration, no edit to `auth.schema.ts`. The seed applies the *existing* committed migrations; it asserts against the schema, never alters it.
- **II. Cloudflare-Native Architecture** — PASS. All D1/R2 access goes through the sanctioned `scripts/common/d1.py` `wrangler` wrapper (the established Python→Cloudflare path); the app under test still uses `getDb()`/`getDocumentsBucket()`. No direct connection construction. No new binding.
- **III. Quality Gates Before Commit** — PASS / reinforces. This feature *is* the test layer the spec explicitly requests, so tests are mandated here. Existing `pnpm lint`/`pnpm format` gates apply; Python files follow repo style; the new layer is additive and the fast unit gates are unchanged (SC-006).
- **IV. Security & Auth by Default** — PASS. No new route, no public exposure. The smoke *exercises* the existing auth gate (asserts the unauthenticated image-route case is non-2xx). Test credentials are synthetic, local-only, never committed as production secrets.
- **V. Simplicity & Incremental Delivery** — PASS. Reuses the existing wrapper, `det_id`, and the already-installed Python Playwright instead of adding `@playwright/test`; one seed module + one integration package + one smoke runner + one CI job. Three independently shippable slices (seed → integration → browser → CI) ordered by priority.

No violations → Complexity Tracking left empty.

## Project Structure

### Documentation (this feature)

```text
specs/046-e2e-smoke-suite/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output (synthetic seed dataset shape)
├── quickstart.md        # Phase 1 output (how to run locally + in CI)
├── contracts/           # Phase 1 output (seed contract + smoke surface contract)
│   ├── seed-contract.md
│   └── smoke-surfaces.md
└── tasks.md             # Phase 2 output (speckit tasks)
```

### Source Code (repository root)

```text
scripts/
├── common/
│   └── d1.py                       # (existing) wrangler wrapper — reused, untouched
├── e2e/                            # NEW — seed + browser smoke (synthetic only)
│   ├── __init__.py
│   ├── seed.py                     # deterministic synthetic D1+R2 seed (CLI: python -m e2e.seed)
│   ├── synthetic.py                # pure dataset builder (det_id rows) — importable, stdlib-only, unit-friendly
│   ├── server.py                   # start/stop `pnpm preview`, wait-for-ready, port + trusted-origin handling
│   ├── auth.py                     # provision synthetic admin user (sign-up + role elevation) via HTTP + wrangler
│   └── smoke.py                    # Python Playwright sync_api browser smoke runner (CLI: python -m e2e.smoke)
├── integration_tests/             # NEW — real-D1 integration tests (separate discovery path)
│   ├── __init__.py
│   ├── _harness.py                 # seed-once-per-module fixture helpers + D1 read assertions
│   ├── test_merge_and_write_d1.py
│   ├── test_mark_pending_d1.py
│   ├── test_build_documents_d1.py
│   └── test_reconcile_cascade_d1.py
└── tests/                          # (existing) unit suite — UNCHANGED

.github/workflows/
└── ci.yml                          # add a second job `e2e` (parallel to `verify`)

package.json                        # add scripts: test:py:integration, e2e:seed, e2e:smoke, test:e2e
```

**Structure Decision**: Single repo, Python test layer under `scripts/`. The seed + browser smoke live in a new `scripts/e2e/` package; the real-D1 integration tests live in a separate `scripts/integration_tests/` discovery path so the existing `pnpm test:py` (`discover -s tests`) is byte-for-byte unchanged and never needs Miniflare. The pure synthetic-dataset builder (`synthetic.py`) is split out from the I/O so it stays import-only and could even be unit-tested, mirroring the `preserve.py`/`reconcile.py` "pure core, thin I/O shell" pattern.

## Phase 0: Outline & Research

All NEEDS CLARIFICATION were resolved in the spec's Clarifications/Assumptions. `research.md` records the resolved decisions (driver choice, test isolation, server lifecycle, synthetic-data guarantee, CI trigger) with rationale + rejected alternatives.

## Phase 1: Design & Contracts

- `data-model.md` — the synthetic seed dataset: every table, the exact synthetic rows (ids via `det_id`), and the relationships that make the browser surfaces light up (the deep-link alert, the over/within documents, the pending vs classified attachments, the page-image keys).
- `contracts/seed-contract.md` — the seed's observable contract (what rows + R2 keys exist after a run; idempotency).
- `contracts/smoke-surfaces.md` — the six browser surface checks + the auth gate, each with its stable assertion anchor.
- `quickstart.md` — local run + CI wiring.
- Agent context update via `update-agent-context.sh`.

## Complexity Tracking

> No constitution violations — table intentionally empty.
