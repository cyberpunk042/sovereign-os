#!/usr/bin/env bash
# scripts/hooks/recurrent/memory-janitor.sh
#
# SDD-071 — the M028 SLM-janitor sweep. Runs one bounded maintenance pass over the memory
# store (memory-janitor.py sweep): global deterministic enrichment (dedup/tag/edges) + SLM
# enrichment (topic/summarize, honest-defer) + a bounded lifecycle advance toward `verify`
# (never auto-promotes/archives). This is the mirror of the SDD-069 observe stream: observe
# admits real events → the janitor enriches + advances them, both on a timer.
#
# Runs from sovereign-memory-janitor.timer (~every 10 min). CLI/timer-only — the sweep
# mutates the memory store, so it is never a web control (R10212). DRY-RUN-safe by default;
# the timer runs it live (--confirm). Idempotent (deterministic jobs + the stop-stage guard).
set -euo pipefail

__SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
__REPO_ROOT="$(cd "${__SCRIPT_DIR}/../../.." && pwd)"
# shellcheck source=../../build/lib/common.sh
. "${__REPO_ROOT}/scripts/build/lib/common.sh"
# shellcheck source=../../build/lib/observability.sh
. "${__REPO_ROOT}/scripts/build/lib/observability.sh"

out="$(python3 "${__REPO_ROOT}/scripts/intelligence/memory-janitor.py" sweep --confirm 2>/dev/null)" || {
  emit_metric sovereign_os_memory_janitor_run_total 1 'result="fail"'
  echo "memory-janitor: sweep failed" >&2
  exit 1
}
count="$(printf '%s' "${out}" | python3 -c 'import sys,json;print(json.load(sys.stdin).get("swept",0))' 2>/dev/null || echo 0)"
emit_metric sovereign_os_memory_janitor_run_total 1 'result="pass"'
emit_metric sovereign_os_memory_janitor_swept_total "${count}" 'result="pass"'
echo "memory-janitor: swept ${count} memory entry/entries (enrich + bounded advance)"
