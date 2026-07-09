#!/usr/bin/env bash
# scripts/hooks/recurrent/memory-observe.sh
#
# SDD-069 — the M028 observation event stream. Tails the OCSF span log
# (/var/log/sovereign-os/spans.jsonl) and feeds each new real system event into the M028
# admission value-gate (memory-observe.py run → memory-admit.admit), so the Memory OS
# self-populates from real activity instead of only CLI-fed observations.
#
# Runs from sovereign-memory-observe.timer (~every 5 min). CLI/timer-only — the engine
# mutates the memory store via admit, so it is never a web control (R10212). Idempotent
# (a persisted cursor + admit's content-dedup); honest-defer when the span log is empty.
set -euo pipefail

__SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
__REPO_ROOT="$(cd "${__SCRIPT_DIR}/../../.." && pwd)"
# shellcheck source=../../build/lib/common.sh
. "${__REPO_ROOT}/scripts/build/lib/common.sh"
# shellcheck source=../../build/lib/observability.sh
. "${__REPO_ROOT}/scripts/build/lib/observability.sh"

out="$(python3 "${__REPO_ROOT}/scripts/intelligence/memory-observe.py" run --confirm 2>/dev/null)" || {
  emit_metric sovereign_os_memory_observe_run_total 1 'result="fail"'
  echo "memory-observe: observation run failed" >&2
  exit 1
}
count="$(printf '%s' "${out}" | python3 -c 'import sys,json;print(json.load(sys.stdin).get("admitted_count",0))' 2>/dev/null || echo 0)"
emit_metric sovereign_os_memory_observe_run_total 1 'result="pass"'
emit_metric sovereign_os_memory_observe_admitted_total "${count}" 'result="pass"'
echo "memory-observe: admitted ${count} observation(s) from the span log"
