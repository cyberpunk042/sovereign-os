#!/usr/bin/env bash
# preflight.sh — increment preflight for cockpit/webapp work (the "avoid conflict" helper).
#
# The recurring pain when several sessions touch the cockpit in parallel is drift:
# the branch falls behind main, or the app-shell block a sibling session churns
# (webapp/_shared/app-shell-snippet.html) drifts from the panels. This runs the
# cheap checks BEFORE the expensive `make test`, so drift is caught early:
#   1. is the branch behind origin/main (rebase needed)?
#   2. app-shell sync   (scripts/webapp/sync-app-shell.py --check)
#   3. doc lints        (round-refs / sdd-index-consistency / e11 coverage / e11-ux-surface)
#
# Exit 0 = green (safe to proceed); non-zero = something needs attention first.
# Usage:  bash scripts/webapp/preflight.sh [--base origin/main] [--no-fetch]
set -uo pipefail

BASE="origin/main"
FETCH=1
while [ $# -gt 0 ]; do
  case "$1" in
    --base) BASE="$2"; shift 2 ;;
    --no-fetch) FETCH=0; shift ;;
    -h|--help) sed -n '2,17p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
    *) echo "unknown arg: $1" >&2; exit 2 ;;
  esac
done

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT" || exit 1
fails=0
line() { printf '%-34s %s\n' "$1" "$2"; }

# 1 — branch freshness vs base
if [ "$FETCH" = 1 ]; then git fetch "${BASE%%/*}" "${BASE#*/}" -q 2>/dev/null || true; fi
if git rev-parse --verify -q "$BASE" >/dev/null; then
  if git merge-base --is-ancestor "$BASE" HEAD; then
    line "branch vs $BASE" "OK    up to date ($(git rev-parse --short "$BASE"))"
  else
    behind="$(git rev-list --count "HEAD..$BASE" 2>/dev/null || echo '?')"
    line "branch vs $BASE" "REBASE NEEDED  ($behind commit(s) behind — git rebase $BASE)"
    fails=$((fails+1))
  fi
else
  line "branch vs $BASE" "SKIP  ($BASE not found locally)"
fi

# 2 — app-shell sync
if out="$(python3 scripts/webapp/sync-app-shell.py --check 2>&1)"; then
  line "app-shell sync" "OK    $(printf '%s' "$out" | tail -1)"
else
  line "app-shell sync" "DRIFT (run: python3 scripts/webapp/sync-app-shell.py --apply)"
  printf '%s\n' "$out" | tail -5 | sed 's/^/    /'
  fails=$((fails+1))
fi

# 2b — helpers sync
if out="$(python3 scripts/webapp/sync-helpers.py --check 2>&1)"; then
  line "helpers sync" "OK    $(printf '%s' "$out" | tail -1)"
else
  line "helpers sync" "DRIFT (run: python3 scripts/webapp/sync-helpers.py --apply)"
  printf '%s\n' "$out" | tail -5 | sed 's/^/    /'
  fails=$((fails+1))
fi

# 3 — doc lints
DOC_LINTS="tests/lint/test_round_refs.py tests/lint/test_sdd_index_consistency.py tests/lint/test_epic_e11_cross_repo_coverage.py tests/lint/test_e11_ux_surface_coverage.py"
if out="$(python3 -m pytest $DOC_LINTS -q 2>&1)"; then
  line "doc lints" "OK    $(printf '%s' "$out" | grep -oE '[0-9]+ passed' | tail -1)"
else
  line "doc lints" "FAIL"
  printf '%s\n' "$out" | grep -E "FAILED|Error" | head -8 | sed 's/^/    /'
  fails=$((fails+1))
fi

echo
if [ "$fails" -eq 0 ]; then
  echo "preflight: GREEN — safe to proceed."
else
  echo "preflight: $fails check(s) need attention before the gate."
fi
exit "$fails"
