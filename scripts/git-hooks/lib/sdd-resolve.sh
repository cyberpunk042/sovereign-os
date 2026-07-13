#!/usr/bin/env bash
# scripts/git-hooks/lib/sdd-resolve.sh — shared hook helper that runs the
# parallel-session SDD-collision auto-resolver after a merge/rebase (SDD-980).
# SOURCED, not executed (it lives under lib/ so the installer's maxdepth-1 glob
# never symlinks it as a git hook).
#
# Why: SDD-100 gives each session a disjoint number band, but a session can still
# take a number out of its band (it happened twice — dup SDD-969, dup SDD-974).
# Two differently-slugged files sharing a number do NOT git-conflict — they just
# coexist — so the mistake only surfaces when the uniqueness lint goes red AFTER
# a pull. This fires the resolver right then: it renumbers the out-of-band
# intruder into its own band (rule in docs/sdd/980-*.md), VERIFIES with the
# uniqueness/contiguity/counts lints, logs to docs/sdd/RESOLUTION-LOG.md, and —
# on any doubt — reverts + warns with the exact manual fix. Silent + fast when
# there is no collision (the common case), so it is safe on every pull.
#
# The resolver leaves its changes UNSTAGED — a hook must never auto-commit; the
# operator reviews `git status` and commits.
#
# sdd_resolve <context>: run the resolver in --apply mode if python3 + the script
# are present. Any output comes from the resolver itself (silent on the happy
# path). Never fails the hook (post-merge/post-rewrite are informational).

sdd_resolve() {
  local context="${1:-git}" root script
  root="$(git rev-parse --show-toplevel 2>/dev/null)" || return 0
  script="${root}/scripts/git/sdd_conflict_resolver.py"
  [ -f "${script}" ] || return 0
  command -v python3 >/dev/null 2>&1 || return 0
  # --apply: auto-resolve unambiguous collisions, verify, log; revert+warn on
  # doubt. Non-zero exit means "unresolved collisions remain" — surface it as a
  # note but do NOT fail the hook.
  if ! python3 "${script}" --apply; then
    printf '   (sovereign-os · %s: SDD collisions need a manual fix — see above + docs/sdd/RESOLUTION-LOG.md)\n' \
      "${context}" >&2
  fi
  return 0
}
