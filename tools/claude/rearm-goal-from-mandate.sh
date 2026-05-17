#!/usr/bin/env bash
# tools/claude/rearm-goal-from-mandate.sh
#
# Re-arms the operator's persistent /goal Stop-hook condition from the
# durable mandate record. Solves the root cause discovered in this
# arc: the harness `/goal` command rejects strings >4000 chars (the
# operator's full mandate was 6967 chars), so the auto-pilot Stop
# hook silently never registered + each turn ended cleanly after
# git-push.
#
# Usage:
#   1. Pipe the output of this script into `/goal` interactively, OR
#   2. Use it from a SessionStart hook to re-arm goal at session start.
#
# What it does:
#   - Reads docs/standing-directives/INDEX.md to find active mandates.
#   - Emits a COMPACT (<4000 char) goal-text that POINTERS at the
#     mandate file rather than inlining the verbatim text.
#   - Includes the structural Epic IDs so condition-evaluators see
#     the workable-pieces decomposition without needing the long form.

set -euo pipefail

__SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
__REPO_ROOT="$(cd "${__SCRIPT_DIR}/../.." && pwd)"
INDEX="${__REPO_ROOT}/docs/standing-directives/INDEX.md"

if [ ! -f "${INDEX}" ]; then
  echo "ERROR ${INDEX} missing — no active mandates to re-arm goal from." >&2
  exit 1
fi

MANDATE=""
EPICS=""
while IFS=$'\t' read -r m e; do
  MANDATE="$m"
  EPICS="$e"
  break
done < <(awk -F'|' '/\| active \|/ {
  gsub(/^[[:space:]]+|[[:space:]]+$/, "", $3);
  gsub(/^[[:space:]]+|[[:space:]]+$/, "", $5);
  if (match($3, /\.\/[^)]+/)) {
    fn = substr($3, RSTART+2, RLENGTH-2);
    printf "%s\t%s\n", fn, $5;
    exit;
  }
}' "${INDEX}")

if [ -z "${MANDATE}" ]; then
  echo "ERROR no active mandate found in ${INDEX}" >&2
  exit 1
fi

cat <<EOF
Continue work toward the standing operator mandate recorded at
docs/standing-directives/${MANDATE}.

Read that file at the start of each session. Pick the next TODO
Module from any Epic. Ship one round per turn (CLI + L3 test +
commit + push), cite the Epic/Module ID in the commit message,
mark the Module ✓ in the mandate file when shipped.

Active epics: ${EPICS}

Rules (sacrosanct):
- never minimize, reduce, conflate, or corrupt the operator's words
- compound mindset — each axis multiplies; plan months not days
- SDD + TDD + SFIF + SRP + OOP + Design Patterns + documentation
- always non-blocking, always toward the goal
- direct push to sovereign-os main; never-ending PR on selfdef cycle-N
- operator keys never in-repo; #![forbid(unsafe_code)] workspace-wide

The mandate is open-ended. Never report "satisfied" or "done" —
each shipped round opens visibility into the next TODO Module.
Continue endlessly until the operator explicitly clears.
EOF
