## User Input

```text
$ARGUMENTS
```

You **MUST** consider the user input before proceeding (if not empty).

## Outline

You are creating or updating the project constitution at `.claude/agent-memory/speckit/constitution.md`. This is the project's **repo-specific memory** — the speckit skill itself ships NO constitution (it is repo-agnostic); every repo keeps its own here. Your job is to (a) collect/derive concrete values for this project, (b) fill the constitution precisely, and (c) propagate any amendments across dependent artifacts.

Follow this execution flow:

1. Load the existing constitution at `.claude/agent-memory/speckit/constitution.md`.
   - **If the file does not exist yet (a fresh repo)**, create it: copy the placeholder skeleton from `.claude/skills/speckit/templates/constitution-template.md` to that path, then fill every `[ALL_CAPS_IDENTIFIER]` token with concrete values derived from the repo (`package.json` scripts / `Makefile` / `pyproject.toml` / `README` / CI config) and the user's input. (The template ships with the skill; the filled constitution lives in repo memory.)
   - If it exists, identify every placeholder token of the form `[ALL_CAPS_IDENTIFIER]` and any stale values.
   **IMPORTANT**: The user might require fewer or more principles than usual. If a number is specified, respect it. Adapt the section count accordingly.

2. Collect/derive values for placeholders:
   - If user input (conversation) supplies a value, use it.
   - Otherwise infer from existing repo context (README, docs, prior constitution versions if embedded).
   - For governance dates: `RATIFICATION_DATE` is the original adoption date (if unknown ask or mark TODO), `LAST_AMENDED_DATE` is today if changes are made, otherwise keep previous.
   - `CONSTITUTION_VERSION` must increment according to semantic versioning rules:
     - MAJOR: Backward incompatible governance/principle removals or redefinitions.
     - MINOR: New principle/section added or materially expanded guidance.
     - PATCH: Clarifications, wording, typo fixes, non-semantic refinements.
   - If version bump type ambiguous, propose reasoning before finalizing.

3. Draft the updated constitution content:
   - Replace every placeholder with concrete text (no bracketed tokens left except intentionally retained template slots that the project has chosen not to define yet—explicitly justify any left).
   - Preserve heading hierarchy and comments can be removed once replaced unless they still add clarifying guidance.
   - Ensure each Principle section: succinct name line, paragraph (or bullet list) capturing non‑negotiable rules, explicit rationale if not obvious.
   - Ensure Governance section lists amendment procedure, versioning policy, and compliance review expectations.
   - **Ensure a "Running & Verifying the App" section** capturing the concrete, copy-pasteable commands an agent needs (derive them from the repo's `package.json` scripts / `Makefile` / `pyproject.toml` / `README` / CI): how to **start the app / dev server**, how to **exercise a change** against local or prod-like data (what surface, what data), and the **lint / format / test** commands to run before opening a PR. This is the project's verification knowledge — the repo-agnostic `speckit pr` phase defers to this section instead of hardcoding any command. (If this project uses a dedicated verification agent/skill, name it here.)

4. Consistency propagation checklist (convert prior checklist into active validations):
   - Read `.claude/skills/speckit/templates/plan-template.md` and ensure any "Constitution Check" or rules align with updated principles.
   - Read `.claude/skills/speckit/templates/spec-template.md` for scope/requirements alignment—update if constitution adds/removes mandatory sections or constraints.
   - Read `.claude/skills/speckit/templates/tasks-template.md` and ensure task categorization reflects new or removed principle-driven task types (e.g., observability, versioning, testing discipline).
   - Read each command file in `.claude/skills/speckit/references/*.md` (including this one) to verify no outdated references (agent-specific names like CLAUDE only) remain when generic guidance is required.
   - Read any runtime guidance docs (e.g., `README.md`, `docs/quickstart.md`, or agent-specific guidance files if present). Update references to principles changed.

5. Produce a Sync Impact Report (prepend as an HTML comment at top of the constitution file after update):
   - Version change: old → new
   - List of modified principles (old title → new title if renamed)
   - Added sections
   - Removed sections
   - Templates requiring updates (✅ updated / ⚠ pending) with file paths
   - Follow-up TODOs if any placeholders intentionally deferred.

6. Validation before final output:
   - No remaining unexplained bracket tokens.
   - Version line matches report.
   - Dates ISO format YYYY-MM-DD.
   - Principles are declarative, testable, and free of vague language ("should" → replace with MUST/SHOULD rationale where appropriate).

7. Write the completed constitution back to `.claude/agent-memory/speckit/constitution.md` (overwrite).

8. Output a final summary to the user with:
   - New version and bump rationale.
   - Any files flagged for manual follow-up.
   - Suggested commit message (e.g., `docs: amend constitution to vX.Y.Z (principle additions + governance update)`).

Formatting & Style Requirements:

- Use Markdown headings exactly as in the template (do not demote/promote levels).
- Wrap long rationale lines to keep readability (<100 chars ideally) but do not hard enforce with awkward breaks.
- Keep a single blank line between sections.
- Avoid trailing whitespace.

If the user supplies partial updates (e.g., only one principle revision), still perform validation and version decision steps.

If critical info missing (e.g., ratification date truly unknown), insert `TODO(<FIELD_NAME>): explanation` and include in the Sync Impact Report under deferred items.

Operate on the file at `.claude/agent-memory/speckit/constitution.md`: update it in place if present, or create it there if absent. Never scatter copies into the skill folder or elsewhere — the speckit skill stays repo-agnostic; the constitution is per-repo memory.
