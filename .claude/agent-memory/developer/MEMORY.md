# Memory Index

- [tools/ module test discovery](tools-module-test-discovery.md) — self-contained `tools/<pkg>/` modules (underscore name, zero scripts/analysis imports); run tests with `-t tools`; prettier covers tools/
- [integration-tests shared-D1 scope](integration-tests-shared-d1-scope.md) — real-D1 integration tests share local Miniflare D1 with non-synthetic data; scope assertions to synthetic ids, never whole-table counts
- [prettier docs CI gate](prettier-docs-ci-gate.md) — CI "Lint, format, tests, typecheck" runs `prettier --check .` over markdown too; doc-touching PRs can pass tests but fail format — run prettier --write before pushing
- [summarize_mismatches empty scope](summarize-mismatches-empty-scope.md) — a falsy attachment_ids/entry_ids ([] or None) means "no scope = ALL findings"; short-circuit to [] yourself when a computed id set is empty
- [EXTRACT-002 vision transcriber](extract002-vision-transcriber.md) — transcribe() seam in tools/doc_transcribe: pluggable cli/api backend, validate-above-backend, claude -p prompt via stdin, anthropic optional/lazy
