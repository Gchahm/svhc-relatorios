# Fix `pnpm` script failures from unapproved build scripts (`ERR_PNPM_IGNORED_BUILDS`)

> Dev-tooling chore. Self-contained — can be handed to `/speckit specify` or done directly as a
> small PR.

## Problem

With pnpm 11.5.2, running any `pnpm <script>` that triggers the dependency-status pre-check
(e.g. `pnpm db:generate`, `pnpm lint`, `pnpm format`) fails:

```
[ERR_PNPM_IGNORED_BUILDS] Ignored build scripts: esbuild@…, msw@…, sharp@…, unrs-resolver@…, workerd@…
Run "pnpm approve-builds" to pick which dependencies should be allowed to run scripts.
… Command failed with exit code 1: '…/pnpm' install
```

pnpm now blocks dependency build scripts until they are explicitly approved. The pre-run
`runDepsStatusCheck` (an implicit `pnpm install`) hits that gate and exits non-zero, so the actual
script (`drizzle-kit generate`, `next lint`, `prettier`) never runs. The script bodies themselves
are fine — invoking the underlying binary directly works:

- `node_modules/.bin/drizzle-kit generate` instead of `pnpm db:generate`
- `node_modules/.bin/prettier --write <files>` instead of `pnpm format`
- `node_modules/.bin/next lint --file <f>` instead of `pnpm lint`

(`npx wrangler d1 migrations apply DATABASE --local` for `db:migrate:dev` is unaffected.)

This was hit during feature `003-vlm-analyze-all-pages`; the workaround above was used and noted
so the migration could still be generated/applied.

## Goal

`pnpm db:generate`, `pnpm lint`, `pnpm format`, and the other `package.json` scripts run cleanly
without the manual `node_modules/.bin` workaround, on a fresh checkout.

## Suggested fix

Add a pnpm build-approval allowlist to `package.json` (no existing `pnpm` config block today):

```jsonc
{
  "pnpm": {
    "onlyBuiltDependencies": ["esbuild", "msw", "sharp", "unrs-resolver", "workerd"]
  }
}
```

Equivalently, run `pnpm approve-builds`, select those packages, and commit the resulting config.
Verify by running `pnpm install` then `pnpm db:generate` on a clean clone — both should succeed
with no `ERR_PNPM_IGNORED_BUILDS`.

## Notes / watch-outs

- Confirm `sharp` / `workerd` actually need their build scripts in this Cloudflare Workers
  (OpenNext) setup before blanket-approving — approving only what's required is preferable.
- Invoking `pnpm` in a sandbox can also auto-create a stray `pnpm-workspace.yaml` stub (placeholder
  `set this to true or false`); it is not part of any feature and should be deleted if it appears.
- Per Constitution Principle III, run `pnpm lint` + `pnpm format` to confirm the gates pass once
  fixed.

## Acceptance

- On a fresh clone, `pnpm install` completes without `ERR_PNPM_IGNORED_BUILDS`.
- `pnpm db:generate`, `pnpm lint`, and `pnpm format` all run their underlying tools successfully
  (no pre-check failure).
- The build-approval config is committed to `package.json` (or `pnpm-workspace.yaml`).
