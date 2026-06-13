# Tasks: Integration/E2E Smoke Suite — Seeded Local D1/R2 + Browser Flows

**Feature**: `046-e2e-smoke-suite` | **Spec**: [spec.md](./spec.md) | **Plan**: [plan.md](./plan.md)

This feature IS the test layer the spec requests, so test code is the deliverable (Constitution III). Tasks are organized by the spec's user stories (US1 seed → US2 integration → US3 browser → US4 CI), priority order.

## Phase 1: Setup

- [x] T001 Create the Python test package skeleton: `scripts/e2e/__init__.py` and `scripts/integration_tests/__init__.py` (empty package markers).
- [x] T002 Add `package.json` scripts (no dep change): `e2e:seed` (`cd scripts && uv run python -m e2e.seed`), `test:py:integration` (`cd scripts && uv run python -m unittest discover -s integration_tests -t .`), `e2e:smoke` (`cd scripts && uv run python -m e2e.smoke`), `test:e2e` (`cd scripts && uv run python -m e2e.smoke --serve`). Run `pnpm format` after.

## Phase 2: Foundational (blocking prerequisites)

- [x] T003 [P] Implement the pure synthetic-dataset builder in `scripts/e2e/synthetic.py`: `build_dataset() -> dict[str, list[dict]]` returning the table→rows dict from data-model.md (period `2099-01`, ids via `det_id`, `EXEMPLO`/`*.svhc.local`/fake-CNPJ markers), `tiny_png() -> bytes` (constant 1×1 PNG), and `image_plan() -> list[tuple[str, str]]` mapping each attachment's R2 key (`2099-01/<entry_id>_p1.png`) to its bytes. Stdlib + `scripts/common` only; no `data/scrape` read.
- [x] T004 Implement `scripts/e2e/seed.py` (CLI `python -m e2e.seed`): refuse `--remote`; run `wrangler d1 migrations apply DATABASE --local`; `d1.upsert_tables(build_dataset(), target="local")`; invoke `analysis.documents.build_documents("local")`; upsert the seeded alerts; `d1.put_object` each image-plan entry (writing bytes to a temp file first). Print a terse summary (rows per table + image count). Depends on T003.

## Phase 3: User Story 1 — Deterministic synthetic seed (P1)

**Goal**: One command provisions a fresh, idempotent, synthetic-only local D1 + R2.
**Independent test**: run `pnpm e2e:seed` on clean state; assert expected row counts + R2 keys; re-run yields identical row set.

- [x] T005 [US1] Implement `scripts/integration_tests/_harness.py`: `seed_once()` (run the seed module's main; cache so a test module seeds once), `q(sql)` thin wrapper over `d1.query(sql, target="local")`, `count(table, where)` helper, and `r2_exists(key)` via `d1.get_object` round-trip into a temp dir. Depends on T004.
- [x] T006 [US1] Implement `scripts/integration_tests/test_seed_d1.py`: assert the seed-contract post-conditions (report=1, entries=6, attachments=5, attachment_state classified/pending split, analyses=3+records=3, documents≥2, the two alerts with `metadata.entry_ids`, each R2 image key present) and idempotency (count + ids stable across two seed runs). Depends on T005.

**Checkpoint**: seed works and is asserted idempotent + synthetic.

## Phase 4: User Story 2 — Python integration tests over real writebacks (P1)

**Goal**: drive the real `scripts/common/d1.py` writebacks against seeded local D1; assert post-state + idempotency.
**Independent test**: `pnpm test:py:integration` green; each named writeback asserted by reading D1 back.

- [x] T007 [P] [US2] `scripts/integration_tests/test_merge_and_write_d1.py`: seed; construct a minimal `attachments.AttachmentAnalysisResult` for the **E4** (pending) attachment with one `PageAnalysisRecord`; call `attachments._merge_and_write(result, target="local")`; assert (a) `attachment_analyses` now has E4's row + its record, (b) `attachment_state.classified_at` for E4 is non-NULL (stamped), (c) the seeded `page_classifications` staging row for E4 is **deleted** (staging consume), all in the one batch; re-run and assert identical state (idempotent).
- [x] T008 [P] [US2] `scripts/integration_tests/test_mark_pending_d1.py`: seed; call `extractions.mark_pending("local", attachment_ids=[<E3 attachment id>])`; assert `attachment_state.classified_at` for E3 is NULL and any E3 `page_classifications` rows are gone; idempotent on re-run.
- [x] T009 [P] [US2] `scripts/integration_tests/test_build_documents_d1.py`: seed; run `python -m analysis build-documents` (subprocess via the module) — assert the over-claim `NF-1001` and within `NF-1002` documents + their `document_entries` exist; then mutate one analysis's `document_number` (write a new key via `d1.execute_sql`), re-run `build-documents`, and assert the now-stale document/link id is **pruned** (no zombie) while the new key's row appears; idempotent on a second identical run.
- [x] T010 [P] [US2] `scripts/integration_tests/test_reconcile_cascade_d1.py`: seed; build `ScrapedIds`/`ExistingRows` for `2099-01` where **E5** vanished from the scrape; call `reconcile.build_reconciliation(...)`; `d1.execute_sql(result.sql, target="local")`; assert E5's `entries` row + its attachment + `attachment_state` + any analysis-owned dependents are cascade-deleted AND a `portal_row_vanished` alert exists for `2099-01`; idempotent on re-run (already-deleted ⇒ no-op, alert still present).

**Checkpoint**: all four real writebacks validated against SQLite, each idempotent.

## Phase 5: User Story 3 — Browser E2E smoke (P2)

**Goal**: the six surface checks (smoke-surfaces.md) pass against the served Workers build.
**Independent test**: `pnpm test:e2e` walks sign-in + gate, entries, deep link + dialog, dead-link notice, documents statuses, image route both ways.

- [x] T011 [US3] Implement `scripts/e2e/server.py`: `serve(port=3000)` context manager that runs `pnpm preview` (cwd repo root) as a process group with `BETTER_AUTH_URL`/trusted-origins set for the port, polls `GET /` until 200/307 (bounded timeout, clear failure message), yields the base URL, and terminates the group on exit.
- [x] T012 [US3] Implement `scripts/e2e/auth.py`: `ensure_admin(base_url)` — `POST {base_url}/api/auth/sign-up/email` with the synthetic admin (idempotent: tolerate "already exists"), then `wrangler d1 execute DATABASE --local --command "UPDATE users SET role='admin' WHERE email='e2e@svhc.local';"` (via `d1.execute_sql` is remote-agnostic — use a direct wrangler call or `d1.execute_sql` against local). Return the credentials.
- [x] T013 [US3] Implement `scripts/e2e/smoke.py` (CLI `python -m e2e.smoke [--serve]`): with optional `serve()`, ensure admin, then run S1a..S6b from smoke-surfaces.md via Playwright `sync_api` (headless Chromium); bounded waits; exit non-zero on first failure naming the surface + expected vs actual; reuse the signed-in context for S6a and a cookie-less request for S6b. Depends on T011, T012, T003 (for E1/E3 ids + analysis id).

**Checkpoint**: full-stack smoke green locally against `pnpm preview` + the seed.

## Phase 6: User Story 4 — CI wiring (P2)

**Goal**: a separate `e2e` CI job, parallel to `verify`, reporting independently.
**Independent test**: open a PR; the `e2e` job seeds, runs integration + smoke; `verify` is unchanged.

- [x] T014 [US4] Add the `e2e` job to `.github/workflows/ci.yml` per smoke-surfaces.md (checkout, pnpm, Node 22, uv+Python 3.12, `pnpm install --frozen-lockfile`, `cd scripts && uv run playwright install --with-deps chromium`, `pnpm db:migrate:dev`, `pnpm e2e:seed`, `pnpm test:py:integration`, `pnpm test:e2e`). Same `on` triggers as `verify`; do not modify the `verify` job. Structure so the trigger alone can later move it to `main`+nightly.

## Phase 7: Polish & Cross-Cutting

- [x] T015 [P] Run `pnpm lint`, `pnpm format`, `pnpm typecheck` (no TS changed but confirm clean) and `pnpm test:py` + `pnpm test:ts` to confirm the fast unit suites are unaffected (SC-006). Add Python files to Prettier ignore only if Prettier touches them inappropriately (it ignores `.py` by default; verify `format:check` stays green).
- [x] T016 [P] Update `CLAUDE.md` "Important Patterns" with a one-paragraph note on the feature-046 E2E/integration layer (seed `scripts/e2e/seed.py`, integration `scripts/integration_tests/`, smoke `scripts/e2e/smoke.py` via Python Playwright, the `e2e` CI job), consistent with the existing feature notes.
- [x] T017 Local verification dry-run: `pnpm e2e:seed` → `pnpm test:py:integration` → `pnpm test:e2e`, capture results for the PR body (the speckit `pr` phase `verify` step).

## Dependencies

- T001 → T002 (setup) → everything.
- T003 (pure dataset) blocks T004 (seed), T007–T010 (need seeded ids), T013 (needs seeded ids).
- T004 (seed) blocks T005/T006 (US1) and is the precondition for all integration tests (T007–T010) and the browser smoke seed.
- US1 (T005–T006) and US2 (T007–T010) can follow once T004 lands; US2 tests are mutually `[P]` (distinct files).
- US3 (T011–T013) depends on the seed + the served app.
- US4 (T014) depends on the local commands existing (T002) and the suites passing (US1–US3).
- Polish (T015–T017) last.

## Parallel opportunities

- T007, T008, T009, T010 are distinct files with no ordering dependence beyond a seeded DB → run/author in parallel.
- T015 and T016 are independent (`[P]`).

## MVP scope

US1 (the seed) + US2 (integration tests) is a shippable MVP: it delivers the real-D1 regression safety the issue prizes most, independent of the browser layer. US3 + US4 complete the issue.
