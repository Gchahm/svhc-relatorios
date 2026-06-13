---
name: extract002-vision-transcriber
description: The EXTRACT-002 transcribe() seam under tools/doc_transcribe — pluggable cli/api backend, validate-above-backend, claude -p via stdin
metadata:
  type: project
---

`tools/doc_transcribe/transcribe.py` is the EXTRACT-002 vision transcriber: `transcribe(image,
doc_type="auto", *, backend="cli", model=None, backend_impl=None) -> {doc_type, schema_version, fields[,
parse_errors]}`. It builds on the EXTRACT-001 contract in the same package (see
[[tools-module-test-discovery]]).

Key seams / gotchas:

- **Validate above the backend.** The `Backend` protocol (`backends.py`) returns only raw JSON *text*;
  `transcribe()` runs `extract_json()` then `validate_transcription()` (the EXTRACT-001 validator) and
  records failures in `parse_errors` — it NEVER raises on a bad *model response*. `TranscribeError`
  (config/usage errors only) is raised at call time, never at import.
- **`cli` backend (default) feeds the prompt via stdin, not a positional arg.** `claude`'s `--add-dir`
  is variadic, so a positional prompt after it is swallowed as another directory → "Input must be
  provided either through stdin or as a prompt argument". Use `subprocess.run(argv, input=prompt, ...)`.
  Invocation: `claude -p --output-format text [--model X] --add-dir <image_dir>` with the prompt on
  stdin; the prompt names the absolute image path so Claude Code's Read tool views it.
- **`anthropic` is an optional extra.** `ApiBackend.transcribe_to_json` imports `anthropic` lazily
  *inside* the method (`importlib.import_module`), so `import doc_transcribe` and the `cli` backend work
  with the SDK absent and no `ANTHROPIC_API_KEY`. `api` backend uses `output_config.format` json_schema
  (wire enforcement), default model `claude-opus-4-8`, adaptive thinking, no `temperature`/`budget_tokens`.
- **Canonical stamping.** `transcribe()` overwrites `fields["doc_type"]`/`["schema_version"]` with the
  registry-canonical values before validating, so a model echoing a wrong type/version can't yield an
  inconsistent result. `auto` reads the model's reported `doc_type` through `canonical_type` (outro
  fallback); a forced type wins regardless of the echo.
- Tests inject a `FakeBackend` (in `tests/_helpers.py`) — no real `claude` subprocess, no API, no
  network. Run with `-t tools` (see [[tools-module-test-discovery]]).
