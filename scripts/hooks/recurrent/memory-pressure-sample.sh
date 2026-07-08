#!/usr/bin/env bash
# scripts/hooks/recurrent/memory-pressure-sample.sh — E1.M15 Layer B sampler.
#
# R269 (scripts/hardware/memory-pressure.py) ships the operator-pull memory
# pressure / OOM watcher (status / psi / oom-events verbs) and even
# structures a `metrics` dict ready for emission — but nothing emitted it,
# so the "+ Layer B metrics" half of E1.M15 was unimplemented: no dashboard
# panel or alert could track memory pressure or OOM kills over time. This
# recurrent hook closes that gap by sampling the watcher every minute and
# emitting its metrics into the node_exporter textfile collector, mirroring
# the R258 wattage-sample pattern.
#
# Honors SOVEREIGN_OS_DRY_RUN=1.

set -euo pipefail

__SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
__REPO_ROOT="$(cd "${__SCRIPT_DIR}/../../.." && pwd)"
# shellcheck source=../../build/lib/common.sh
. "${__REPO_ROOT}/scripts/build/lib/common.sh"
# shellcheck source=../../build/lib/observability.sh
. "${__REPO_ROOT}/scripts/build/lib/observability.sh"

log_step_header "memory-pressure-sample" \
  "per-minute memory-pressure / OOM Layer B sample (E1.M15)"

probe="${__REPO_ROOT}/scripts/hardware/memory-pressure.py"
if [ ! -x "${probe}" ]; then
  log_error "missing ${probe} — R269 memory-pressure absent"
  exit 1
fi

# Informational verb — rc=0 even when PSI/cgroup unavailable.
status_rc=0
status_json="$(python3 "${probe}" status --json 2>/dev/null)" || status_rc=$?
if [ "${status_rc}" -ne 0 ]; then
  log_warn "status probe rc=${status_rc} — emitting unavailable sentinels"
  status_json='{"verdict":"unavailable","metrics":{}}'
fi

# Parse the fields. PSI is null when the kernel lacks /proc/pressure
# (pre-4.20); emit -1 as the "unavailable" sentinel so the series is always
# present (mirrors the audit-chain == -1 convention) rather than absent.
read -r avail_pct swap_pct psi_some psi_full oom_kills verdict_code <<<"$(
  STATUS_JSON="${status_json}" python3 -c '
import json, os
d = json.loads(os.environ["STATUS_JSON"])
m = d.get("metrics") or {}
def num(v, default):
    return default if v is None else v
avail = num(m.get("mem_available_pct"), 0)
swap = num(m.get("swap_used_pct"), 0)
some = num(m.get("psi_some_avg60_pct"), -1)
full = num(m.get("psi_full_avg10_pct"), -1)
oom = (m.get("cgroup_oom_kill_count") or 0) + (m.get("journal_oom_event_count") or 0)
verdict = d.get("verdict", "unavailable")
code = {"ok": 0, "attention": 1, "critical": 2}.get(verdict, -1)
print(f"{avail} {swap} {some} {full} {oom} {code}")
')"

avail_pct="${avail_pct:-0}"
swap_pct="${swap_pct:-0}"
psi_some="${psi_some:--1}"
psi_full="${psi_full:--1}"
oom_kills="${oom_kills:-0}"
verdict_code="${verdict_code:--1}"

emit_metric_set memory-pressure-sample \
  "# HELP sovereign_os_memory_available_pct E1.M15: RAM available as percent of total (MemAvailable/MemTotal)." \
  "# TYPE sovereign_os_memory_available_pct gauge" \
  "sovereign_os_memory_available_pct ${avail_pct}" \
  "# HELP sovereign_os_memory_swap_used_pct E1.M15: swap used as percent of total swap (0 when no swap)." \
  "# TYPE sovereign_os_memory_swap_used_pct gauge" \
  "sovereign_os_memory_swap_used_pct ${swap_pct}" \
  "# HELP sovereign_os_memory_psi_some_avg60_pct E1.M15: PSI some-stall avg60 for memory (-1 = PSI unavailable, pre-4.20 kernel)." \
  "# TYPE sovereign_os_memory_psi_some_avg60_pct gauge" \
  "sovereign_os_memory_psi_some_avg60_pct ${psi_some}" \
  "# HELP sovereign_os_memory_psi_full_avg10_pct E1.M15: PSI full-stall avg10 for memory (-1 = PSI unavailable). full>0 means EVERY task stalled on memory." \
  "# TYPE sovereign_os_memory_psi_full_avg10_pct gauge" \
  "sovereign_os_memory_psi_full_avg10_pct ${psi_full}" \
  "# HELP sovereign_os_memory_oom_kill_count E1.M15: OOM kills observed (cgroup v2 memory.events oom_kill + journal scan)." \
  "# TYPE sovereign_os_memory_oom_kill_count gauge" \
  "sovereign_os_memory_oom_kill_count ${oom_kills}" \
  "# HELP sovereign_os_memory_pressure_verdict E1.M15: 0=ok 1=attention 2=critical -1=unavailable (matches memory-pressure.py status verdict)." \
  "# TYPE sovereign_os_memory_pressure_verdict gauge" \
  "sovereign_os_memory_pressure_verdict ${verdict_code}" \
  "sovereign_os_memory_sample_last_run_timestamp $(date +%s)"

log_info "  available=${avail_pct}% swap=${swap_pct}% psi_some=${psi_some} psi_full=${psi_full} oom=${oom_kills} verdict=${verdict_code}"
exit 0
