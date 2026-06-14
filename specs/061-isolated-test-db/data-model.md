# Phase 1 Data Model: Isolated local test database

This feature introduces **no persisted data entities** (no D1 schema change, no migration). The
"entities" are dev-environment configuration artifacts.

## Configuration entities

### Persist selector (`SVHC_WRANGLER_PERSIST`)

- **Kind**: process environment variable.
- **Domain**: unset, or a directory path (relative or absolute).
- **Semantics**:
  - Unset ⇒ wrangler default state (`.wrangler/state` = staging). No `--persist-to` flag added.
  - Set + `target == "local"` ⇒ wrangler local state redirected to the resolved directory.
  - `target == "remote"` ⇒ selector ignored entirely (never redirected).
- **Resolution**: a relative value is resolved against the repo root (`_REPO_ROOT`); an absolute value
  is used as-is.

### State directories

| Directory | Role | Written by | Gitignored |
|-----------|------|------------|------------|
| `.wrangler/state` | Staging DB (D1 + R2 + KV) | All non-test local commands (the human) | yes (`.wrangler`) |
| `.wrangler/state-test` | Test DB (D1 + R2 + KV) | test/seed/e2e suites + `db:migrate:test` | yes (`.wrangler`) |

## Derived value: `_persist_args(target)`

A pure function in `scripts/common/d1.py`:

```
_persist_args(target) -> list[str]
  if target != "local":            return []        # remote never redirected
  raw = env["SVHC_WRANGLER_PERSIST"]
  if not raw:                       return []        # unset (or empty) ⇒ staging default
  dir = raw if absolute else _REPO_ROOT / raw       # relative ⇒ repo root
  return ["--persist-to", str(dir)]
```

Appended to every local wrangler argv the wrapper builds (execute / query / R2 put / R2 get).

## State transitions

None. The selector is read fresh per wrangler invocation; there is no stored state, no migration, no
lifecycle.
