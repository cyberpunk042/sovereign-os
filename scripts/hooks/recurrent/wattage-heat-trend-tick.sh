#!/usr/bin/env bash
# scripts/hooks/recurrent/wattage-heat-trend-tick.sh — E1.M36 trend driver.
#
# R316 (scripts/hardware/wattage-heat-trend-watcher.py) ships the rolling-
# window trend classifier (wattage / cpu_temp / gpu_temp → stable / climbing
# / climbing-fast), but E1.M36 calls for a "real-time periodic-sample daemon"
# that "emits the trend verdict" — and nothing ran it on a cadence and
# nothing emitted its verdict, so it only advanced when the operator manually
# typed `tick`, and no dashboard/alert could see a climbing trend. This
# recurrent hook closes both halves: it drives a `tick` every minute (so the
# rolling window actually fills) and emits the per-signal + overall trend
# verdicts as Layer B metrics, mirroring the wattage-sample pattern.
#
# Honors SOVEREIGN_OS_DRY_RUN=1.

set -euo pipefail

__SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
__REPO_ROOT="$(cd "${__SCRIPT_DIR}/../../.." && pwd)"
# shellcheck source=../../build/lib/common.sh
. "${__REPO_ROOT}/scripts/build/lib/common.sh"
# shellcheck source=../../build/lib/observability.sh
. "${__REPO_ROOT}/scripts/build/lib/observability.sh"

log_step_header "wattage-heat-trend-tick" \
  "per-minute wattage+heat trend tick + Layer B verdict (E1.M36)"

probe="${__REPO_ROOT}/scripts/hardware/wattage-heat-trend-watcher.py"
if [ ! -x "${probe}" ]; then
  log_error "missing ${probe} — R316 wattage-heat-trend-watcher absent"
  exit 1
fi

tick_rc=0
tick_json="$(python3 "${probe}" tick --json 2>/dev/null)" || tick_rc=$?
if [ "${tick_rc}" -ne 0 ]; then
  log_warn "tick rc=${tick_rc} — emitting unknown sentinels"
  tick_json='{"verdict":"unknown","trends":{}}'
fi

# Map each verdict/trend string to a numeric code so it is alertable:
#   stable=0  climbing=1  climbing-fast=2  insufficient-data/unknown=-1
read -r v_overall v_watt v_cpu v_gpu <<<"$(
  TICK_JSON="${tick_json}" python3 -c '
import json, os
d = json.loads(os.environ["TICK_JSON"])
code = {"stable": 0, "climbing": 1, "climbing-fast": 2}
def c(s):
    return code.get(s, -1)
tr = d.get("trends") or {}
def trend_of(sig):
    return c((tr.get(sig) or {}).get("trend"))
vals = [
    c(d.get("verdict")),
    trend_of("wattage_w"),
    trend_of("cpu_temp_c"),
    trend_of("gpu_temp_c"),
]
print(" ".join(str(x) for x in vals))
')"

v_overall="${v_overall:--1}"
v_watt="${v_watt:--1}"
v_cpu="${v_cpu:--1}"
v_gpu="${v_gpu:--1}"

emit_metric_set wattage-heat-trend \
  "# HELP sovereign_os_wattage_heat_trend_verdict E1.M36: overall trend 0=stable 1=climbing 2=climbing-fast -1=insufficient/unknown." \
  "# TYPE sovereign_os_wattage_heat_trend_verdict gauge" \
  "sovereign_os_wattage_heat_trend_verdict ${v_overall}" \
  "# HELP sovereign_os_wattage_heat_trend_wattage E1.M36: PSU wattage trend code (same 0/1/2/-1 scale)." \
  "# TYPE sovereign_os_wattage_heat_trend_wattage gauge" \
  "sovereign_os_wattage_heat_trend_wattage ${v_watt}" \
  "# HELP sovereign_os_wattage_heat_trend_cpu_temp E1.M36: CPU temperature trend code (same scale)." \
  "# TYPE sovereign_os_wattage_heat_trend_cpu_temp gauge" \
  "sovereign_os_wattage_heat_trend_cpu_temp ${v_cpu}" \
  "# HELP sovereign_os_wattage_heat_trend_gpu_temp E1.M36: GPU temperature trend code (same scale). Watch wattage climbing while gpu_temp lags — power rising faster than heat dissipates." \
  "# TYPE sovereign_os_wattage_heat_trend_gpu_temp gauge" \
  "sovereign_os_wattage_heat_trend_gpu_temp ${v_gpu}" \
  "sovereign_os_wattage_heat_trend_last_run_timestamp $(date +%s)"

log_info "  verdict=${v_overall} wattage=${v_watt} cpu=${v_cpu} gpu=${v_gpu}"
exit 0
