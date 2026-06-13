<!--
Worker catch-up prompt for the `developer` agent (resume a live worker, or respawn after one died).
Read by the implement-loop skill; substitute the {{…}} placeholders before passing as the agent's
prompt (when respawning) or as the SendMessage body (when resuming a live worker).
Placeholders: {{ISSUE_NUMBER}}, {{ISSUE_TITLE}}, {{BRANCH}}, {{PR}}
-->
Recover in-progress work on GitHub issue #{{ISSUE_NUMBER}} ("{{ISSUE_TITLE}}"). A previous worker
stopped and its PR is no longer being watched. Existing branch: {{BRANCH}}. PR: #{{PR}}.

First, re-arm your lifetime heartbeat (step 0 — the background loop touching your per-issue file
`.cache/implement-loop/heartbeat-{{ISSUE_NUMBER}}`); a previous worker's loop died with it, so the
dispatcher needs a fresh one to see you are alive again.

Do NOT restart from scratch. Reconstruct state first: check out {{BRANCH}}, read the issue
(`gh issue view {{ISSUE_NUMBER}} --comments`), the spec under `specs/{{BRANCH}}/`, and the FULL PR
review thread (note what has already been addressed). Then resume your standing watcher protocol:
settle the existing thread **body-first** — a self-authored `COMMENTED` review whose body starts
`VERDICT: approve` IS the approval, so if it stands at the current head commit, squash-merge
immediately; otherwise address the requested changes, push, and re-arm the watcher.

Your final message must be ONLY the terse JSON result, exactly as in your standing protocol.
