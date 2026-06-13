# Quickstart: running the CI gates locally

The CI workflow runs exactly the commands below. To reproduce a green check before pushing:

```bash
# From the repo root
pnpm install --frozen-lockfile   # match CI's install

pnpm lint            # ESLint
pnpm format:check    # Prettier read-only check (NEW script)
pnpm test:ts         # node --test "src/**/*.test.mjs"
pnpm test:py         # stdlib unittest under scripts/ via uv
pnpm typecheck       # tsc --noEmit (NEW script)
```

If `pnpm <script>` fails on an ignored-build sandbox, call the binaries directly:

```bash
node_modules/.bin/next lint
node_modules/.bin/prettier --check .
node --test "src/**/*.test.mjs"
( cd scripts && uv run python -m unittest discover -s tests -t . )
node_modules/.bin/tsc --noEmit
```

## If `format:check` flags files

Run `pnpm format` (i.e. `prettier --write .`) to fix, then re-check. CI never auto-formats — fixing
formatting is the author's job. Note: a leftover `.next.broken.*` directory from a failed local build
is ignored by `.prettierignore`/`.gitignore` and won't be flagged.

## Validating the workflow YAML

```bash
python -c "import yaml; yaml.safe_load(open('.github/workflows/ci.yml')); print('YAML OK')"
```

## Maintainer follow-up (out of scope for the workflow file)

Once the `CI` check has run green at least once, mark it **required** on `main`:
Settings → Branches → Branch protection rules → `main` → Require status checks to pass → select `CI`.
