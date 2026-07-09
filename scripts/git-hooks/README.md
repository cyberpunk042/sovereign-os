# sovereign-os git hooks

Operator-side git hooks that gate commits with the same checks CI runs.
Direct-push-to-main workflow (per operator-authorized convention) means
the pre-commit hook is the **only** pre-merge enforcement layer — strongly
recommended to install.

## Install

```sh
scripts/git-hooks/install.sh           # all hooks
scripts/git-hooks/install.sh pre-commit  # just one
```

Idempotent — re-running re-links existing hooks.

## Available hooks

### `pre-commit`

Runs before every commit:

1. **Layer 1 lint** — `pytest tests/schema tests/lint` (~25 cases)
2. **Profile validation** — `scripts/validate-profiles.sh` (schema +
   resolved with mixins for all 5 profiles)
3. **shellcheck** — warning-only (mirrors CI)
4. **L3 fast sample** — common_lib + state_lib + observability_lib +
   orchestrator_dry_run

Exits non-zero on failure. Bypass once with `git commit --no-verify`
(use sparingly; CI will fail anyway).

Env vars:
- `SOVEREIGN_OS_PRECOMMIT_SKIP_L3=1` — skip the L3 sample (faster for
  doc-only commits)
- `SOVEREIGN_OS_PRECOMMIT_FULL=1` — run the entire L3 suite (~30+
  seconds; matches CI exactly)

### `post-merge` + `post-rewrite`

Fire after `git pull` / `git merge` (`post-merge`) and after `git rebase` /
`git commit --amend` (`post-rewrite`). They **warn** — never block — when the
operation left git-**tracked** files owned by someone other than the repo owner,
i.e. **git was run as root (`sudo git …`)**.

Why it matters: `sudo git pull` writes the worktree as root, leaving root-owned
files that block normal edits (`Permission denied`), silently drop tool writes,
and break the build/panel tooling. One root pull once left 482 files `root:root`
and stalled a whole session. The hook surfaces it immediately with the exact fix:

```sh
sudo chown -R <owner>:<group> <repo>
```

They are **silent when ownership is clean**, and deliberately ignore transient
artifacts (`__pycache__/*.pyc`, `node_modules`, …) — only tracked files count.
Shared logic lives in `lib/ownership-warn.sh` (sourced, never installed as a hook).

## Why?

The sovereign-os repo runs direct-push-to-main per the operator's
authorized workflow. There's no PR review gate; CI catches failures
after push. The pre-commit hook brings the gate forward so:

- Operator sees broken state BEFORE pushing (local reproduction faster
  than CI cycle)
- 10 real wiring bugs caught by the L3 discipline so far would have
  been caught at commit time too (with the L3 sample)
- Profile validation prevents schema-conformance regressions slipping
  past

## Uninstall

```sh
rm .git/hooks/pre-commit .git/hooks/post-merge .git/hooks/post-rewrite
```

The hooks are symlinks; removing the link leaves the source in
`scripts/git-hooks/` untouched.
