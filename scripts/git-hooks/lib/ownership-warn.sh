#!/usr/bin/env bash
# scripts/git-hooks/lib/ownership-warn.sh — shared warning for the post-merge
# and post-rewrite hooks. SOURCED, not executed (it lives under lib/ so the
# installer's maxdepth-1 glob never symlinks it as a git hook).
#
# Why this exists (operator footgun, 2026-07-09): running `sudo git pull` /
# `sudo git rebase` writes the updated worktree AS ROOT, leaving root-owned files
# that block normal edits ("Permission denied"), silently drop sed/Edit writes,
# and break tooling. One root pull left 482 files root:root and stalled a whole
# work session. This surfaces the problem the instant it happens, with the exact
# one-line fix — so it's never a silent mystery again.
#
# ownership_warn <context>: if the worktree now contains files NOT owned by the
# repo's own directory owner, print a loud, actionable warning to stderr. Silent
# (no output) when ownership is clean — so it only ever speaks up on a real problem.

ownership_warn() {
  local context="${1:-git}" root owner group foreign n
  root="$(git rev-parse --show-toplevel 2>/dev/null)" || return 0
  owner="$(stat -c '%U' "${root}" 2>/dev/null)" || return 0
  group="$(stat -c '%G' "${root}" 2>/dev/null || echo "${owner}")"
  [ -n "${owner}" ] || return 0

  # Check ONLY git-TRACKED files — exactly what a pull/rebase writes. This
  # deliberately ignores transient artifacts (__pycache__/*.pyc, node_modules,
  # …) which become root-owned merely by running python/node as root — a
  # different, harmless thing that would otherwise false-alarm every time.
  foreign="$( (cd "${root}" && git ls-files -z 2>/dev/null \
      | xargs -0 -r stat -c '%U|%n' 2>/dev/null) \
      | awk -F'|' -v o="${owner}" '$1 != o { print $2 }' )"
  [ -n "${foreign}" ] || return 0
  n="$(printf '%s\n' "${foreign}" | grep -c .)"
  local ylw red rst
  ylw=$'\033[33m'; red=$'\033[1;31m'; rst=$'\033[0m'
  {
    echo ""
    echo "${red}⚠  sovereign-os · ${context}: ${n} file(s) here are NOT owned by '${owner}'.${rst}"
    echo "${ylw}   You most likely ran git as root (sudo git …). Root-owned files block${rst}"
    echo "${ylw}   normal edits (Permission denied), silently drop tool writes, and break${rst}"
    echo "${ylw}   the build/panel tooling. Restore ownership now:${rst}"
    echo ""
    echo "     ${red}sudo chown -R ${owner}:${group} ${root}${rst}"
    echo ""
    echo "${ylw}   Then always run git as '${owner}', never root, so this can't recur.${rst}"
    echo ""
  } >&2
}
