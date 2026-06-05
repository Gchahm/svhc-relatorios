# Feature Hand-off Inbox

This folder is a **hand-off queue** between agents. When the PM agent (`.claude/agents/pm.md`)
recommends a next feature and the maintainer accepts it, the PM agent writes a self-contained
feature description here. A _separate_ agent — the one that owns the spec-driven (speckit)
workflow — later picks it up and runs `speckit specify` from it.

The two agents run in **separate contexts** and never call each other directly (Claude Code
subagents cannot spawn other subagents). This folder is the only channel between them.

## Why the `_` prefix

`specs/_handoff/` is deliberately prefixed with an underscore so it never matches speckit's
spec/branch glob (`^[0-9]{3}-`). This keeps pending hand-offs from colliding with real spec
directories (`specs/001-...`, `specs/002-...`) and keeps `create-new-feature.sh` auto-numbering
correct.

## File format

One file per accepted recommendation:

```
specs/_handoff/<slug>.md
```

Each file follows the contract in
`specs/001-repo-self-assessment/contracts/handoff-feature.md` — YAML frontmatter
(`slug`, `title`, `status: pending`, `source_report`, `created`) plus `Summary`,
`Problem & Goal Link`, and `Scope Notes` sections. The `Summary` is written to be usable directly
as the argument to `speckit specify`, with no dependency on the PM agent's session.

## Consuming a hand-off (spec-running agent)

```
Read specs/_handoff/<slug>.md and run /speckit specify using its Summary as the feature description.
```

Once a real `specs/<NNN>-<slug>/` spec exists, the consumer may mark or remove the hand-off file.
