# Phase 0 Research: Vision transcriber module (EXTRACT-002)

All NEEDS CLARIFICATION items from the spec/clarify phase are resolved here.

## Decision 1 — Backend interface seam

**Decision**: A minimal `Backend` Protocol with one method `transcribe_to_json(image_bytes, media_type,
schema, instruction) -> str` returning the raw JSON text the model produced. `transcribe()` resolves
the type → schema, builds the instruction (shared `prompts.py`), calls the selected backend, then
validates above it. The backend is injectable (a constructor/argument) so tests pass a `FakeBackend`.

**Rationale**: Keeps validation/registry/error-capture in one place (`transcribe.py`), independent of
which backend ran (FR-004). The seam returns raw text (not a parsed dict) so the JSON-extraction +
parse-error handling lives above the backend uniformly — the `cli` backend has no wire enforcement, so
the module's own parse+validate layer is mandatory (design §11.3).

**Alternatives considered**: Backend returns a parsed dict — rejected: the `cli` backend's output is
free-form text that may wrap JSON in prose/fences, so the extraction step belongs above the backend,
once, not duplicated. A class hierarchy with abstract base — rejected as heavier than a `Protocol`.

## Decision 2 — `cli` backend mechanics (`claude -p`)

**Decision**: Shell out to `claude -p --output-format text --model <model> --add-dir <image_dir>
"<instruction naming the image path>"` via `subprocess.run` (captured stdout, timeout, no shell=True).
The instruction tells the local Claude Code session to Read the image at the given path and emit ONLY
the JSON for the resolved type's schema. The image is written to a temp file when bytes are passed; a
path is used directly (and its parent dir is `--add-dir`'d so the Read tool can access it). `--model`
maps `opus`→default alias; the session uses whatever model it is configured with otherwise. No
`ANTHROPIC_API_KEY` and no `anthropic` import are touched on this path (FR-005, FR-007, SC-002).

**Rationale**: Matches the repo's current auth posture (existing Claude Code login, no new secret) and
the design's default. Running in a subprocess keeps the image out of any orchestrator's context (§11.1).
`--output-format text` returns the model's text answer directly; we extract JSON from it.

**Alternatives considered**: `--output-format json` (wrapper with a `result` field) — usable but adds a
second unwrap; `text` + robust extraction is simpler and the extraction is needed anyway for fenced
output. Passing the image as base64 in the prompt — rejected: `claude` reads files via its Read tool;
a path + `--add-dir` is the idiomatic, token-cheaper path.

## Decision 3 — JSON extraction from `cli` text (clarify Q1)

**Decision**: Best-effort, pure helper `extract_json(text) -> dict | None`: (1) strip a leading/trailing
markdown code fence (```` ```json `` … `` ``` ````), (2) `json.loads` the whole thing; on failure (3)
scan for the largest balanced top-level `{...}` substring and `json.loads` that. Return `None` if
nothing parses. `transcribe()` then: parsed dict → validate; `None` → return an `outro` best-effort
object (`{doc_type: "outro", schema_version, raw_text: <the text>}`) with a `parse_errors` entry. Never
raises (FR edge cases, SC-005).

**Rationale**: Models occasionally wrap JSON in prose/fences; a garbled response must not crash a bulk
run. Pure + stdlib → unit-testable without a subprocess.

**Alternatives considered**: Strict `json.loads` only — rejected (too brittle for the `cli` path). A
regex for ```` ``` ````-fenced blocks only — rejected: balanced-brace scan also recovers bare-prose-wrapped JSON.

## Decision 4 — `api` backend mechanics (Anthropic SDK)

**Decision**: `ApiBackend` lazily imports `anthropic` **inside** its method (not at module top), so the
package imports without the SDK (FR-007). It builds a single non-streaming
`client.messages.create(model=<claude-opus-4-8 default>, max_tokens=..., thinking={"type":"adaptive"},
output_config={"format":{"type":"json_schema","schema":<type schema>}}, messages=[{image block + text
instruction}])`, reads the JSON text from the response, returns it. Image is sent as a base64 `image`
content block with its media type. `ANTHROPIC_API_KEY` is read from the env by the SDK; if missing, a
clear error is raised before the call (clarify Q3 / FR-006). Model default `claude-opus-4-8`, overridable
(spec Assumption / design T4).

**Rationale**: `output_config.format` json_schema enforces the typed shape at the wire (SC-003), then the
module re-validates above the backend (FR-003). Single-call extraction is the right surface (design
§11.3). Lazy import keeps the SDK optional. Per the `claude-api` skill: adaptive thinking on Opus 4.8,
no `temperature`/`budget_tokens`, structured outputs via `output_config.format`.

**Alternatives considered**: `messages.parse()` (Zod/typed helper) — Python uses `output_config.format`
on `create()` with a raw JSON schema, which is what we have; `parse()` adds a typed-model layer we don't
need (we validate with our own stdlib validator). Streaming — unnecessary for a single bounded extraction.

## Decision 5 — Optional-dependency + missing-key errors

**Decision**: Define a `TranscribeError` (subclass of `RuntimeError`). Selecting `backend="api"` with
`anthropic` not importable raises `TranscribeError("the 'api' backend requires the anthropic SDK; install
the api extra (pip install anthropic)")`. Missing `ANTHROPIC_API_KEY` raises
`TranscribeError("the 'api' backend requires ANTHROPIC_API_KEY")`. The `cli` backend raises a
`TranscribeError` if the `claude` binary is not on PATH. These are raised at call time, never at import
(FR-007).

**Rationale**: A clear, actionable error beats an opaque top-level `ImportError`/`KeyError`. Raising at
call time (not import) preserves SC-002 (module imports clean without the SDK/key).

## Decision 6 — Result envelope vs EXTRACT-001 flat shape (spec Assumption)

**Decision**: `transcribe()` returns a `dict` `{"doc_type": <canonical>, "schema_version": SCHEMA_VERSION,
"fields": <the full EXTRACT-001-conformant object>, "parse_errors": [...] (only if non-empty)}`. `fields`
is exactly what `validate_transcription(fields, doc_type)` validates — the EXTRACT-001 object carrying its
own `doc_type`/`schema_version`/`raw_text` + type blocks. Top-level `doc_type`/`schema_version` mirror the
authoritative canonical values. The transcriber **overwrites** `fields["doc_type"]` and
`fields["schema_version"]` with the canonical/registry values before validating (clarify Q2 / FR-011 /
edge cases), so a model echoing a wrong version/type can't produce an inconsistent result.

**Rationale**: Direct reuse of the EXTRACT-001 validator with no reshaping; the top-level mirror gives
callers a convenient `result["doc_type"]` without digging into `fields`. Stamping canonical values keeps
`doc_type`/`schema_version` authoritative regardless of backend.

**Alternatives considered**: `fields` = type blocks only (without the envelope) — rejected: would require
re-wrapping before validation and diverge from how `validate_transcription` consumes a payload.

## Decision 7 — Type resolution & `auto`

**Decision**: `doc_type="auto"` (default) → no caller-forced type; the model's reported `doc_type` (read
from the returned JSON, run through `canonical_type`, falling back to `outro`) wins. An explicit
`doc_type` (e.g. `"recibo"`) → `canonical_type(doc_type)` is forced as the result type and the model is
instructed to transcribe into that type's schema; the result's `doc_type` is the forced canonical value
regardless of what the model echoes (clarify Q2). Unknown/None always → `outro` (registry never raises).

**Rationale**: Mirrors the registry's `canonical_type`/`schema_for` semantics (EXTRACT-001) and the design's
`doc_type?: ...|"auto"` interface.

## Decision 8 — Testing without a subprocess/network

**Decision**: A `FakeBackend(canned_json: str)` implements the `Backend` protocol and returns the canned
string; `test_transcribe.py` drives all result-assembly/validation/parse-error/type-resolution paths
through it. `test_backends.py` unit-tests the **pure** pieces of each backend without executing them:
`extract_json` cases (clean, fenced, prose-wrapped, garbage→None), the `cli` argv builder, the `api`
request-body builder (image block + json_schema format), and the optional-dep/key error branches (by
monkeypatching `importlib`/`os.environ`/`shutil.which`). `test_cli.py` invokes the CLI `main([...])` with
an injected fake backend and asserts stdout JSON + exit codes. No real `claude`, no Anthropic API, no
network (FR-012, SC-001..SC-005).

**Rationale**: The repo convention is stdlib `unittest` driving pure seams with injected providers
(CLAUDE.md feature 044; EXTRACT-001 tests). Keeps CI deterministic and dependency-free.
