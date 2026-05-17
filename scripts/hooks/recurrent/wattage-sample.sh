#!/usr/bin/env bash
# scripts/hooks/recurrent/wattage-sample.sh — R258 (SDD-026 Z-18 sampler).
#
# Operator-named (verbatim, 2026-05-17 expansion): "real time tracking
# and intelligence around it. (Possibly heat too I guess)".
#
# R252 ships the on-demand `power-status budget` probe. R253 wires the
# graceful-shutdown timer. R258 closes the time-series gap: a recurrent
# hook that samples the wattage budget every minute + emits 4 Layer B
# metrics so the operator's dashboard graphs power-over-time without
# the operator pasting `watch -n 1 ...` into a tmux pane.
#
# Honors SOVEREIGN_OS_DRY_RUN=1.

set -euo pipefail

__SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
__REPO_ROOT="$(cd "${__SCRIPT_DIR}/../../.." && pwd)"
# shellcheck source=../../build/lib/common.sh
. "${__REPO_ROOT}/scripts/build/lib/common.sh"
# shellcheck source=../../build/lib/observability.sh
. "${__REPO_ROOT}/scripts/build/lib/observability.sh"

STEP_ID="wattage-sample"
log_step_header "${STEP_ID}" "R258: per-minute PSU wattage sample → Layer B metrics"

if [ -n "${SOVEREIGN_OS_DRY_RUN:-}" ]; then
  log_info "DRY-RUN — would call R252 power-status budget --json + emit:"
  log_info "  sovereign_os_power_estimated_load_watts"
  log_info "  sovereign_os_power_headroom_watts"
  log_info "  sovereign_os_power_utilization_pct"
  log_info "  sovereign_os_power_sample_last_run_timestamp"
  exit 0
fi

probe="${__REPO_ROOT}/scripts/hardware/power-status.py"
if [ ! -x "${probe}" ]; then
  log_error "missing ${probe} — R252 power-status absent"
  exit 1
fi

# Call budget; rc=0 always (informational verb).
budget_rc=0
budget_json="$(python3 "${probe}" budget --json 2>/dev/null)" || budget_rc=$?
if [ "${budget_rc}" -ne 0 ]; then
  log_warn "budget probe rc=${budget_rc} — emitting zero metrics"
  budget_json='{"estimated_load_watts":0,"headroom_watts":0,"utilization_pct":0}'
fi

read -r load headroom util <<<"$(BUDGET_JSON="${budget_json}" python3 -c '
import json, os
d = json.loads(os.environ["BUDGET_JSON"])
load = d.get("estimated_load_watts") or 0
head = d.get("headroom_watts") or 0
util = d.get("utilization_pct") or 0
print(f"{load} {head} {util}")
')"

# When PSU not declared, headroom comes back as None → "" — coerce to 0.
load="${load:-0}"
headroom="${headroom:-0}"
util="${util:-0}"

emit_metric_set wattage-sample \
  "# HELP sovereign_os_power_estimated_load_watts R258: live aggregate of R219 GPU draw + declared CPU TDP + overhead." \
  "# TYPE sovereign_os_power_estimated_load_watts gauge" \
  "sovereign_os_power_estimated_load_watts ${load}" \
  "# HELP sovereign_os_power_headroom_watts R258: PSU sustained budget minus estimated load." \
  "# TYPE sovereign_os_power_headroom_watts gauge" \
  "sovereign_os_power_headroom_watts ${headroom}" \
  "# HELP sovereign_os_power_utilization_pct R258: estimated load as percent of PSU sustained budget." \
  "# TYPE sovereign_os_power_utilization_pct gauge" \
  "sovereign_os_power_utilization_pct ${util}" \
  "sovereign_os_power_sample_last_run_timestamp $(date +%s)"

log_info "  load=${load}W headroom=${headroom}W util=${util}%"
exit 0
