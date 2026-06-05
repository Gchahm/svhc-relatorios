# Full Speckit Pipeline (One-Shot)

Execute the complete spec-driven development workflow for: **$ARGUMENTS**

## Execution Mode

**CRITICAL**: This is a ONE-SHOT execution. After the initial specification phase, run ALL subsequent phases automatically with NO interruptions, NO confirmations, and NO pauses until the entire workflow completes.

## Pipeline Phases

Execute these phases in sequence:

### Phase 1: Specify (ONLY phase that may ask questions)
- Run `speckit specify` with the provided description
- This is the ONLY phase where clarifying questions are permitted
- Once the spec is written, proceed immediately to Phase 2

### Phase 2: Clarify (automatic)
- Run `speckit clarify` automatically
- Do NOT pause for review
- Do NOT ask for confirmation
- Proceed immediately to Phase 3

### Phase 3: Plan (automatic)
- Run `speckit plan` automatically
- Do NOT pause for review
- Do NOT ask for confirmation
- Proceed immediately to Phase 4

### Phase 4: Tasks (automatic)
- Run `speckit tasks` automatically
- Do NOT pause for review
- Do NOT ask for confirmation
- Proceed immediately to Phase 5

### Phase 5: Implement (automatic)
- Run `speckit implement` automatically
- Complete ALL tasks without stopping
- Do NOT ask for confirmation between tasks
- Proceed immediately to Phase 6

### Phase 6: PR (automatic)
- Run `speckit pr` automatically
- Push specs to specs repo main
- Create PR in service repo with spec link
- Report final PR URL

## Rules

1. **No interruptions**: After Phase 1 completes, execute Phases 2-6 without ANY user interaction
2. **No confirmations**: Do not ask "Should I proceed?" or "Ready to continue?"
3. **No reviews**: Do not pause to show intermediate outputs or ask for review
4. **Error handling**: If a phase fails, attempt to fix the issue and continue. Only stop if the error is unrecoverable.
5. **Completion**: Report a final summary ONLY after ALL phases complete

## Final Output

After all phases complete, provide a single summary:
- Spec location
- PR URL
- Spec URL
- Brief list of what was implemented

## Example

```
speckit full PLT-2343 Build user preference endpoints for theme and notification settings
```

This will run the entire pipeline and only stop to report the final PR URL.
