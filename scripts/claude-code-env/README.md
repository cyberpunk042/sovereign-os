# scripts/claude-code-env/ — bulletproof Claude Code user-environment

> Idempotent install for the operator-side overrides that defeat the
> Claude Code cloud harness's opinionated defaults and the env-runner's
> stop-hook script re-staging glitch. Reapply in one command after any
> container rebuild, fresh clone, or settings drift.

## What this installs

Four files into `~/.claude/`:

| File | Mode | Purpose |
|------|------|---------|
| `settings.json` | 600 | Empty `Stop`/`SubagentStop` hook arrays (defeats template merge) + raised env-var caps for `blocking_limit` / `max_turns` / `prompt_too_long` stop-reasons |
| `CLAUDE.md` | 644 | User-global operator overrides — including the override of the harness's "always create draft PR" default |
| `stop-hook-git-check.sh` | 755 | Neutralized version (`exit 0`) — env-runner re-stages this each session, but explicit empty hook arrays in settings.json prevent it being wired regardless |
| `validate-stop-hook-fix.sh` | 755 | 5-check validator runnable in human / `--json` / `--quiet` modes |

## Usage

```bash
# From the info-hub repo root:
bash scripts/claude-code-env/apply.sh

# Dry-run (report-only, no changes):
bash scripts/claude-code-env/apply.sh --dry-run

# Skip the post-install validator (faster, less verification):
bash scripts/claude-code-env/apply.sh --no-validate

# Show inline docs:
bash scripts/claude-code-env/apply.sh --help
```

## Idempotency

Running `apply.sh` twice is a no-op the second time:

- Each template is compared (via `cmp -s`) against the live target.
- **Absent** → install.
- **Identical** → skip (only chmod if perms drift).
- **Differs** → back up live to `~/.claude/backups/<file>.<UTC-timestamp>.bak`, install template.

The post-install validator (`~/.claude/validate-stop-hook-fix.sh`) is run
automatically and its exit code is propagated. Validator exit codes:
`0` all pass / `1` at least one check failed / `2` jq missing or
settings.json unreadable.

## When to reapply

| Trigger | Why |
|---------|-----|
| Fresh container / new cloud session VM | The env-runner re-stages the stop-hook script; raised caps + hooks override survive in `settings.json` but worth verifying |
| `~/.claude/settings.json` got clobbered (e.g. via Claude Code's `/config` UI) | Template hook reactivates if user overrides lost |
| Stop-hook validator (`~/.claude/validate-stop-hook-fix.sh`) reports drift | Drift detected; reapply restores canonical state |
| Adding a new override to the templates | Push template change, run apply.sh on each environment |
| Onboarding a new ecosystem-project's container | Single-command bring-up for the operator's standard environment |

## Updating the templates

The templates in `templates/` are the canonical source. To update:

1. Edit the live file in `~/.claude/`.
2. Verify it works (run the validator + smoke-test the change).
3. Copy back to `templates/`:
   ```bash
   cp ~/.claude/<file> scripts/claude-code-env/templates/<file>
   ```
4. Commit + push. Future `apply.sh` runs on other environments pick up
   the new canonical state.

## Source-of-truth lesson

The forensic finding that motivated this scripted setup is in the
second-brain at:

```
wiki/lessons/01_drafts/claude-code-env-runner-restages-stop-hook-script-from-baked-template-at-every-session-start.md
```

It covers: the env-runner Go binary's role in re-staging, file-birth
forensics proving the re-stage timing, why deletion / image-edit /
binary-edit are all infeasible, the two-part durable fix recipe, and
the bash exit-code-capture gotcha caught during validator development.

## Hidden harness defaults this overrides

The Claude Code cloud/remote-execution harness ships a system prompt
(NOT user-controllable) with opinionated defaults:

| Hardcoded behavior | Override applied via |
|--------------------|----------------------|
| "Always create PR as draft after push" | `~/.claude/CLAUDE.md` — draft is a SIGNAL, not a default; choose per-PR based on actual readiness |
| Stop-hook re-staged with `exit 2` on dirty git state | `settings.json` empty hooks arrays + neutralized `stop-hook-git-check.sh` |
| Default `CLAUDE_CODE_STOP_HOOK_BLOCK_CAP=8` (cuts long sessions via `blocking_limit`) | `settings.json` env → 1000 |
| Default low `MAX_TURNS` (cuts long sessions via `max_turns`) | `settings.json` env → 10000 |
| Auto-compact enabled by default (cuts long sessions via `prompt_too_long`) | `settings.json` env → `DISABLE_AUTOCOMPACT=1` (DISABLED, per operator standing directive — not throttled via `CLAUDE_CODE_AUTO_COMPACT_WINDOW`) |

`rapid_refill_breaker` (service-side rate limit, `CLAUDE_CODE_RATE_LIMIT_TIER`
is observation-only) is NOT client-tunable; out of scope.
