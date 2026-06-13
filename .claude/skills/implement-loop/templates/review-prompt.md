<!--
Reviewer dispatch prompt for the `reviewer` agent (one per PR head that needs review).
Read by the implement-loop skill; substitute the {{…}} placeholders before passing as the agent's prompt.
Placeholders: {{PR_NUMBER}}, {{ISSUE_NUMBER}}
-->
Review pull request #{{PR_NUMBER}} (which closes issue #{{ISSUE_NUMBER}}) at its current head commit.

First arm your lifetime heartbeat (step 0 of your standing protocol — the background loop touching
`.cache/implement-loop/review-heartbeat-{{PR_NUMBER}}`), then invoke the `pr-review` skill with
`{{PR_NUMBER}}` and follow it exactly: skip if this head was already reviewed, otherwise post ONE
review with inline comments and a verdict (`REQUEST_CHANGES`, or `APPROVE` / `VERDICT: approve` with
`commit_id` at the head you reviewed — load-bearing for the merge gate).

You only post the review; the developer worker addresses changes and merges. Your final message must
be ONLY the terse one-line verdict.
