# reviewer memory — svhc-relatorios

Durable review gotchas for this repo. Read before reviewing; append what you learn. Keep entries
terse; the canonical conventions live in `CLAUDE.md` (auto-loaded) — record here only what isn't
obvious from it.

## Verdict mechanics

- Single GitHub account: GitHub forbids formal self-approval, so an approval is posted as a
  `COMMENT` review whose **body starts `VERDICT: approve`** (and a change request as
  `VERDICT: request-changes`). The merge gate reads exactly that, with `commit_id` = the reviewed
  head. The `pr-review` skill handles this — don't hand-roll it.

<!-- Add a topic file per durable learning and index it here: - [slug](slug.md) — one-line hook -->
