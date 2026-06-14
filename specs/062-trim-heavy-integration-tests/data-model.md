# Data Model: Trim the 3 heavy integration modules + drop npx wrangler overhead

No persisted data model changes. No D1 schema change, no migration, no Drizzle edit. The synthetic `2099-01` seed (`scripts/e2e/synthetic.py`) and `_harness.py` are unchanged.

## Test-fixture entities (existing, for reference)

| Synthetic id | Role | Used by |
|---|---|---|
| **E3** | Singleton attachment (NF-1002, no shared-NF sibling) | reclassify subject; re_derive `_classify_e3` subject |
| **E4** | PENDING single-entry attachment, own shared-NF representative (page `p1`) | typed-record subject |
| **E1 / E2** | Shared-NF pair (NF-1001) | re_derive group test; reclassify bystander (E1) |

## Code constant (new)

| Symbol | Module | Meaning |
|---|---|---|
| `_WRANGLER` | `scripts/common/d1.py` | `[<repo>/node_modules/.bin/wrangler]` if present, else `["npx", "wrangler"]`. Prepended to every wrangler shell-out. Resolved once at import. |
