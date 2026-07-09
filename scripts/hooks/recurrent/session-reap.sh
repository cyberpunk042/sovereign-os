#!/usr/bin/env bash
# scripts/hooks/recurrent/session-reap.sh
#
# SDD-065 — the M057 session reaper. Archives `active` sessions in
# /run/sovereign-os/sessions.json whose tracked process has already exited
# (crashed / finished without a clean `sessions stop`). This is a
# state-reconciliation janitor: the process is gone regardless, so setting the
# entry's state to `archived` is safe bookkeeping, not a destructive action.
#
# Runs from sovereign-session-reaper.timer (~every 2 min). CLI/timer-only — the
# reaper adds NO web mutation path (R10212); `sessions start` stays CLI-only.
set -euo pipefail

__SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
__REPO_ROOT="$(cd "${__SCRIPT_DIR}/../../.." && pwd)"
# shellcheck source=../../build/lib/common.sh
. "${__REPO_ROOT}/scripts/build/lib/common.sh"
# shellcheck source=../../build/lib/observability.sh
. "${__REPO_ROOT}/scripts/build/lib/observability.sh"

out="$(python3 "${__REPO_ROOT}/scripts/lifecycle/session-runtime.py" reap 2>/dev/null)" || {
  emit_metric sovereign_os_session_reaper_run_total 1 'result="fail"'
  echo "session-reap: reaper invocation failed" >&2
  exit 1
}
count="$(printf '%s' "${out}" | python3 -c 'import sys,json;print(json.load(sys.stdin).get("count",0))' 2>/dev/null || echo 0)"
emit_metric sovereign_os_session_reaper_run_total 1 'result="pass"'
emit_metric sovereign_os_session_reaper_reaped_total "${count}" 'result="pass"'
echo "session-reap: archived ${count} exited session(s)"
