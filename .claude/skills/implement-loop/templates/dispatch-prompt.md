<!--
Worker dispatch prompt for the `developer` agent (initial, per-issue).
Read by the implement-loop skill; substitute the {{…}} placeholders before passing as the agent's prompt.
Placeholders: {{ISSUE_NUMBER}}, {{ISSUE_TITLE}}
-->
You own GitHub issue #{{ISSUE_NUMBER}} ("{{ISSUE_TITLE}}") from spec to merged PR, working directly
in the repo checkout — it is yours alone for this issue's lifetime.

Arm your lifetime heartbeat first (step 0 of your standing protocol — the background loop that
touches your per-issue file `.cache/implement-loop/heartbeat-{{ISSUE_NUMBER}}`), then follow your
protocol, starting from `gh issue view {{ISSUE_NUMBER}} --comments`:
run the speckit `full` pipeline (include `Closes #{{ISSUE_NUMBER}}` in the PR body), verify the change
in the running app against the local data, then watch your own PR and squash-merge it on approval.

You are unattended — make reasonable assumptions and record them in the spec; never ask clarifying
questions. Keep all heavy context (spec, diffs, review threads) in your own context.

Your final message — sent only when the PR merged or you are unrecoverably stuck — must be ONLY:
{"issue": {{ISSUE_NUMBER}}, "pr": <pr-number>, "status": "merged"}
(or {"issue": {{ISSUE_NUMBER}}, "pr": <pr-or-null>, "status": "error", "reason": "<one line>"}).
