# Tasks: Standalone vision transcriber module (image → typed JSON)

**Feature**: 052-vision-transcriber | **Spec**: [spec.md](./spec.md) | **Plan**: [plan.md](./plan.md)

All paths are under `tools/doc_transcribe/`. The EXTRACT-001 files (`registry.py`, `validator.py`,
`schemas/`, `examples/`) are **unchanged**. Tests run with
`uv run python -m unittest discover -s tools/doc_transcribe/tests -t tools`.

## Phase 1: Setup

- [ ] T001 Confirm baseline: run `uv run python -m unittest discover -s tools/doc_transcribe/tests -t tools` (EXTRACT-001 suite green) and confirm `claude` is on PATH (`which claude`); record nothing if both pass.

## Phase 2: Foundational (blocking prerequisites)

- [ ] T002 Create `tools/doc_transcribe/prompts.py` — a pure `build_instruction(schema: dict, doc_type: str) -> str` that returns the shared transcription instruction (transcribe the page into JSON conforming to the given schema for `doc_type`/"auto"; record everything including the full `raw_text`; emit ONLY the JSON object; do NOT compute/derive reconciliation values — transcribe-only per FR-008). Stdlib-only; no imports from `scripts/analysis`.
- [ ] T003 Create `tools/doc_transcribe/backends.py` skeleton — define `TranscribeError(RuntimeError)`, the `Backend` Protocol (`transcribe_to_json(*, image_bytes, media_type, schema, instruction) -> str`), the pure helper `extract_json(text: str) -> dict | None` (strip leading/trailing ```` ``` ````/```` ```json ```` fence → `json.loads`; on failure scan for the largest balanced top-level `{...}` and parse; return `None` if nothing parses), and `media_type_for(path_or_bytes) -> str` (png/jpeg/webp/gif from extension or magic bytes, default `image/png`). Stdlib only at module top (no `anthropic`).

## Phase 3: User Story 1 — cli backend + library `transcribe()` (Priority: P1) 🎯 MVP

**Goal**: `transcribe(image, doc_type="auto")` returns validated typed JSON via the default `cli`
backend, with no `anthropic` SDK and no `ANTHROPIC_API_KEY`, recording validation failures in
`parse_errors` instead of raising.

**Independent test**: `transcribe(image)` with an injected `FakeBackend` returns `{doc_type,
schema_version, fields}` validating clean against the registry schema (no `parse_errors`); a
missing-required / wrong-type backend response yields a non-empty `parse_errors` without raising;
`import doc_transcribe` + a cli `transcribe()` work with `anthropic` absent and the key unset.

- [ ] T004 [US1] Implement `CliBackend` in `tools/doc_transcribe/backends.py` — `__init__(self, model: str | None = None)`; `transcribe_to_json(...)`: raise `TranscribeError` if `shutil.which("claude")` is None; write `image_bytes` to a `tempfile` (suffix from `media_type`) if a path wasn't supplied; build argv `["claude", "-p", "--output-format", "text", *( ["--model", self.model] if self.model else [] ), "--add-dir", <image_dir>, <instruction naming the absolute image path>]`; `subprocess.run(..., capture_output=True, text=True, timeout=...)`; raise `TranscribeError` on non-zero exit; return stdout. No `anthropic` import on this path.
- [ ] T005 [US1] Implement `transcribe()` in `tools/doc_transcribe/transcribe.py` — signature `transcribe(image, doc_type="auto", *, backend="cli", model=None, backend_impl=None) -> dict`; read image bytes + media type (path or bytes; raise `TranscribeError` on missing/unreadable file); build `backend_impl` from `backend` (`"cli"`→`CliBackend(model)`, `"api"`→`ApiBackend(model or default)`, else `TranscribeError`) when not injected; resolve type/schema, call backend, run `extract_json`, assemble + validate + stamp per the contract (research Decisions 6 & 7); return `{doc_type, schema_version, fields[, parse_errors]}`. Import `schema_for`/`canonical_type`/`SCHEMA_VERSION` from `.registry` and `validate_transcription` from `.validator`.
- [ ] T006 [US1] Implement the `auto` / forced-type / `outro`-fallback resolution and the canonical stamping inside `transcribe()` (research Decision 7): forced `doc_type` → `canonical_type(doc_type)` wins; `auto` → `canonical_type(fields.get("doc_type"))` (default `outro`), reload `schema_for` if it changed; always set `fields["doc_type"]=dt` and `fields["schema_version"]=SCHEMA_VERSION` before validating. Handle `extract_json`→`None` by returning an `outro` best-effort result + `parse_errors=["backend returned no parseable JSON"]`.
- [ ] T007 [P] [US1] Update `tools/doc_transcribe/__init__.py` — re-export `transcribe`, `TranscribeError`, `Backend`, `CliBackend`, `ApiBackend` (lazy-safe), `extract_json`; extend `__all__`. Importing the package must NOT import `anthropic`.
- [ ] T008 [P] [US1] Add `FakeBackend` helper to `tools/doc_transcribe/tests/_helpers.py` — implements `Backend`, `__init__(self, canned_json: str)`, `transcribe_to_json(...)` returns the canned string and records the args it was called with (for assertions). Add a tiny sample-image-bytes constant (a 1×1 PNG) so tests can pass real bytes.
- [ ] T009 [US1] Write `tools/doc_transcribe/tests/test_transcribe.py` — cover (INV-1/4/5, US1 acceptance): clean result validates with no `parse_errors`; forced `doc_type="recibo"` resolves canonical + validates against recibo schema; `auto` picks up the model's reported type; missing-required / wrong-type backend JSON → non-empty `parse_errors`, no raise; non-JSON backend response → `outro` best-effort + `parse_errors`; `result["schema_version"]==SCHEMA_VERSION` and `result["doc_type"]` canonical even when the canned JSON echoes a bogus type/version; `raw_text` present in `fields` (FR-009). Drive everything via injected `FakeBackend`.
- [ ] T010 [P] [US1] Write `tools/doc_transcribe/tests/test_backends.py` `extract_json` + `CliBackend` cases — `extract_json` for: clean JSON, ```` ```json ````-fenced, prose-wrapped, leading/trailing whitespace, garbage→`None`; `CliBackend` raises `TranscribeError` when `claude` is absent (monkeypatch `shutil.which`); `CliBackend` builds the expected argv (monkeypatch `subprocess.run` to capture argv and return a fake CompletedProcess) and returns stdout; non-zero exit → `TranscribeError`.
- [ ] T011 [P] [US1] Add a no-`anthropic`/no-key import+transcribe test (INV-2/SC-002) in `test_backends.py` (or a dedicated `test_optional_dep.py`) — assert `import doc_transcribe` succeeds and a `cli` `transcribe(bytes, backend_impl=FakeBackend(...))` works with `ANTHROPIC_API_KEY` removed from `os.environ` and `anthropic` made unimportable (monkeypatch `sys.modules`/`builtins.__import__`). Also assert no module under `tools/doc_transcribe/` imports `scripts.analysis` (grep-style check over the package files, INV-6).

**Checkpoint**: P1 is independently shippable — the reusable `cli`-backend transcriber works end-to-end.

## Phase 4: User Story 2 — api backend with wire-enforced schema (Priority: P2)

**Goal**: `transcribe(image, backend="api")` calls the Anthropic Messages API with the type's schema as
`output_config.format` json_schema, re-validates above the backend, and fails clearly when the optional
SDK / key is missing.

**Independent test** (client stubbed): the request body carries an image block + the type's schema as
the structured-output format; selecting `api` without the SDK importable raises `TranscribeError`
("install the api extra"); without `ANTHROPIC_API_KEY` raises `TranscribeError`.

- [ ] T012 [US2] Implement `ApiBackend` in `tools/doc_transcribe/backends.py` — `__init__(self, model: str = "claude-opus-4-8")`; a pure `build_request(*, image_bytes, media_type, schema, instruction) -> dict` returning the `messages.create` kwargs (model, `max_tokens`, `thinking={"type":"adaptive"}`, `output_config={"format":{"type":"json_schema","schema":schema}}`, `messages=[{"role":"user","content":[{image base64 block}, {text instruction}]}]`) — no SDK import needed to build it; `transcribe_to_json(...)`: raise `TranscribeError` if `anthropic` not importable (lazy `importlib.import_module`); raise `TranscribeError` if `ANTHROPIC_API_KEY` unset; construct the client, call `client.messages.create(**build_request(...))`, extract the JSON text from the response content, return it. Per the `claude-api` skill: Opus 4.8 default, adaptive thinking, no `temperature`/`budget_tokens`, `output_config.format`.
- [ ] T013 [US2] Write `tools/doc_transcribe/tests/test_backends.py` `ApiBackend` cases (INV-3/7) — `build_request` puts the schema under `output_config.format.json_schema` and includes a base64 image block + text instruction; `transcribe_to_json` raises `TranscribeError` with an actionable message when `anthropic` is unimportable (monkeypatch import) and when `ANTHROPIC_API_KEY` is unset; with a stubbed `anthropic` module + a fake client returning canned JSON, `transcribe_to_json` returns that JSON. Also assert `transcribe(..., backend="api", backend_impl=ApiBackend(...))` round-trips through the api path with the client stubbed (re-validation above the backend, SC-003).

**Checkpoint**: P2 layered on P1 — both backends interchangeable behind one interface.

## Phase 5: User Story 3 — CLI (Priority: P2)

**Goal**: `python -m doc_transcribe --image <path> [--type] [--backend] [--model]` prints the typed-JSON
result to stdout (exit 0), errors to stderr (non-zero) on config/usage failures.

**Independent test**: CLI `main([...])` with an injected fake backend prints the `transcribe()` result
as one JSON object and exits 0; missing image / bad backend prints a message to stderr and exits
non-zero; a model-bad-response (with `parse_errors`) still exits 0.

- [ ] T014 [US3] Create `tools/doc_transcribe/__main__.py` — `main(argv: list[str] | None = None) -> int` using `argparse` (`--image` required, `--type` default `auto`, `--backend` default `cli`, `--model` optional, plus a hidden `backend_impl` injection seam for tests via a module-level default); call `transcribe(...)`; `print(json.dumps(result, ensure_ascii=False, indent=2))` to stdout, return 0; catch `TranscribeError` → print to stderr, return 2. `if __name__ == "__main__": sys.exit(main())`.
- [ ] T015 [P] [US3] Write `tools/doc_transcribe/tests/test_cli.py` — `main(["--image", <tmp png>])` with an injected `FakeBackend` prints valid JSON to stdout (capture) and returns 0; a `FakeBackend` returning invalid JSON → result with `parse_errors`, still exit 0; missing image path → exit non-zero + stderr message; unknown `--backend` → exit non-zero.

## Phase 6: Polish & cross-cutting

- [ ] T016 [P] Update `tools/doc_transcribe/README.md` — add an "EXTRACT-002: transcriber" section documenting `transcribe()`, the CLI, the two backends (cli default / api optional extra), the result envelope + `parse_errors`, the no-`anthropic`/no-key invariant, and the test command. Note the directory-name underscore caveat already covered.
- [ ] T017 [P] Add a project memory note under `.claude/agent-memory/developer/` capturing the EXTRACT-002 transcriber seam (cli `claude -p` backend default, api Anthropic-SDK optional, validate-above-backend, `extract_json` recovery) and link it from `MEMORY.md` — only if non-obvious from the code.
- [ ] T018 Run `pnpm format` (prettier covers `tools/` json+md) and `uv run python -m unittest discover -s tools/doc_transcribe/tests -t tools`; fix any failures. Confirm `import doc_transcribe` works with `anthropic` uninstalled.
- [ ] T019 Manual verification: run `python -m doc_transcribe --image <a real page .png>` against a live page (cli backend) and confirm it prints a typed result; record the outcome in the PR body (per the pr phase).

## Dependencies & order

- **Setup (T001)** → **Foundational (T002–T003)** → **US1 (T004–T011)** → **US2 (T012–T013)** →
  **US3 (T014–T015)** → **Polish (T016–T019)**.
- US1 is the MVP and is independently shippable. US2 and US3 both depend only on the Foundational +
  US1 surfaces (the `transcribe()` function + backend seam); they are independent of each other.
- `[P]` tasks within a phase touch different files and can run in parallel (e.g. T007/T008 with T009;
  T010/T011; T016/T017).

## Parallel execution examples

- US1: after T005/T006 land, T007 (`__init__`), T008 (`_helpers`), T010, T011 can proceed in parallel
  with writing T009.
- Polish: T016 (README) and T017 (memory note) are independent of each other.

## Implementation strategy

Ship US1 first (the default `cli` backend + library function — the reusable MVP). Layer US2 (api
backend) and US3 (CLI) on top. Tests are written within each story's phase (FR-012). Keep every module
file free of `scripts/analysis` imports and of a top-level `anthropic` import.
