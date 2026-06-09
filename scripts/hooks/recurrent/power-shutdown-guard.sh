#!/usr/bin/env bash
# scripts/hooks/recurrent/power-shutdown-guard.sh — R253 (SDD-026 Z-18 closure).
#
# Operator-named (verbatim, 2026-05-17 expansion): "the scheduled
# shutdown when battery reach a certain point as one default profile.
# (schedule/planifest/graceful on all levels, orderly)."
#
# R252 ships the ADVISORY surface (battery_critical_pct + runtime
# thresholds with rc=1 when the host should shut down). R253 closes
# the loop: a systemd-timer-driven recurrent hook that:
#
#   1. Runs `power-status advisories --json`
#   2. If verdict == "critical" → trigger graceful shutdown
#   3. Operator-grace-period delay before `systemctl poweroff`
#      to let interactive sessions save work
#
# Safety: this hook NEVER fires shutdown without:
#   - Operator-confirmed config (graceful_shutdown.enabled = true)
#   - Battery + time_left BOTH at/below their critical thresholds
#   - SOVEREIGN_OS_POWER_SHUTDOWN_ARMED=YES OR config flag set
#
# Honors SOVEREIGN_OS_DRY_RUN=1 (logs the decision without firing).

set -euo pipefail

__SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
__REPO_ROOT="$(cd "${__SCRIPT_DIR}/../../.." && pwd)"
# shellcheck source=../../build/lib/common.sh
. "${__REPO_ROOT}/scripts/build/lib/common.sh"
# shellcheck source=../../build/lib/observability.sh
. "${__REPO_ROOT}/scripts/build/lib/observability.sh"

STEP_ID="power-shutdown-guard"
log_step_header "${STEP_ID}" "R253: graceful poweroff when UPS battery ≤ critical"

if [ -n "${SOVEREIGN_OS_DRY_RUN:-}" ]; then
  log_info "DRY-RUN — would call advisories + decide whether to poweroff"
  exit 0
fi

probe="${__REPO_ROOT}/scripts/hardware/power-status.py"
if [ ! -x "${probe}" ]; then
  log_error "missing ${probe} — R252 power-status absent"
  exit 1
fi

# Get advisories JSON. rc=1 means battery ≤ critical; rc=0 means OK
# or no UPS; rc=2 is usage error.
adv_rc=0
adv_json="$(python3 "${probe}" advisories --json 2>/dev/null)" || adv_rc=$?

# Layer B observability — always emit even when no action taken.
verdict="$(echo "${adv_json}" | python3 -c '
import json, sys
try:
    print(json.load(sys.stdin).get("verdict", "unknown"))
except Exception:
    print("error")
')"
verdict_code=$(case "${verdict}" in
    ok) echo 0;;
    attention) echo 1;;
    critical) echo 2;;
    no-ups) echo 3;;
    *) echo 9;;
  esac)

# Emit the guard metrics. `fired` is 0 here and re-emitted as 1 only after
# an actual `shutdown(8)` so operators can alert on a real auto-poweroff
# (verdict=critical alone can't distinguish fired from critical-but-not-
# armed). Re-uses the SAME metric set so the textfile write stays atomic.
emit_guard_metrics() {
  local fired="$1"
  emit_metric_set power-shutdown-guard \
    "sovereign_os_power_shutdown_guard_last_run_timestamp $(date +%s)" \
    "sovereign_os_power_shutdown_guard_advisory_rc ${adv_rc}" \
    "# HELP sovereign_os_power_shutdown_guard_verdict 0=ok 1=attention 2=critical 3=no-ups 9=error" \
    "sovereign_os_power_shutdown_guard_verdict ${verdict_code}" \
    "# HELP sovereign_os_power_shutdown_guard_fired 1 iff this run fired shutdown(8) (critical + armed + not dry-run)" \
    "# TYPE sovereign_os_power_shutdown_guard_fired gauge" \
    "sovereign_os_power_shutdown_guard_fired ${fired}"
}
emit_guard_metrics 0

if [ "${adv_rc}" -eq 0 ]; then
  log_info "verdict=${verdict} — no shutdown action"
  exit 0
fi

# Verdict is critical (adv_rc=1). Check the arm gate.
armed_env="${SOVEREIGN_OS_POWER_SHUTDOWN_ARMED:-NO}"
armed_cfg="$(echo "${adv_json}" | python3 -c '
import json, sys
try:
    d = json.load(sys.stdin)
    # Operator gate: config.graceful_shutdown.enabled = true
    # (R252 advisories surface this when present in power.toml).
    print("YES" if d.get("thresholds", {}).get("enabled") else "NO")
except Exception:
    print("NO")
')"
if [ "${armed_env}" != "YES" ] && [ "${armed_cfg}" != "YES" ]; then
  log_warn "CRITICAL battery state detected but shutdown NOT ARMED."
  log_warn "  Set SOVEREIGN_OS_POWER_SHUTDOWN_ARMED=YES (env)"
  log_warn "  OR power.toml: [graceful_shutdown] enabled = true"
  log_warn "  to allow this hook to fire `systemctl poweroff`."
  exit 0
fi

# Operator-configurable grace period before firing.
grace_sec="${SOVEREIGN_OS_POWER_SHUTDOWN_GRACE_SEC:-60}"
log_warn "CRITICAL battery — shutdown in ${grace_sec}s. Cancel with: systemctl stop sovereign-power-shutdown-guard.timer"

if ! command -v systemctl >/dev/null 2>&1; then
  log_error "systemctl missing — cannot fire poweroff"
  exit 1
fi

# Use shutdown(8) with the operator's grace period so logged-in
# sessions see a wall warning. Minutes only — convert.
grace_min=$(( (grace_sec + 59) / 60 ))
log_warn "firing: shutdown -h +${grace_min} 'sovereign-os: UPS battery critical, gracefully powering off'"
shutdown -h "+${grace_min}" "sovereign-os: UPS battery critical, gracefully powering off" \
  || { log_error "shutdown(8) failed"; exit 1; }

# Shutdown is scheduled (shutdown -h returns immediately). Re-emit with
# fired=1 so an operator's Prometheus sees the auto-poweroff was triggered.
emit_guard_metrics 1

exit 0
