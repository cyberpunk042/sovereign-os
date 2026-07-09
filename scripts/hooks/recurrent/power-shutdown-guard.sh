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

# DRY-RUN no longer short-circuits: it runs the FULL decision (advisories +
# verdict + warning fan-out + orchestrator PLAN) so operators can preview exactly
# what a real critical event would do — without any poweroff. The destructive
# steps (shutdown lock, real orchestrator apply, fallback shutdown) are the only
# things gated on non-dry-run below; the warn helper + orchestrator both honor
# SOVEREIGN_OS_DRY_RUN themselves.
DRY="${SOVEREIGN_OS_DRY_RUN:-}"
[ -n "${DRY}" ] && log_info "DRY-RUN — computing verdict, fanning warnings + showing the orchestrator plan; NO poweroff"

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

# ── state: warning dedup + shutdown re-entry lock ──────────────────────────
GUARD_STATE_DIR="/var/lib/sovereign-os"
LAST_VERDICT_FILE="${GUARD_STATE_DIR}/power-guard-verdict"
SHUTDOWN_LOCK="/run/sovereign-os/shutdown-in-progress"
WARN="${__REPO_ROOT}/scripts/power/graceful-warn.sh"
ORCHESTRATOR="${__REPO_ROOT}/scripts/power/schedule-manifest.py"
last_verdict="$(cat "${LAST_VERDICT_FILE}" 2>/dev/null || echo "")"
_save_verdict() {
  mkdir -p "${GUARD_STATE_DIR}" 2>/dev/null || true
  # subshell so a redirection failure (e.g. read-only dir) is fully suppressed
  ( printf '%s\n' "${verdict}" > "${LAST_VERDICT_FILE}" ) 2>/dev/null || true
}
_warn() { [ -x "${WARN}" ] && "${WARN}" "$@" || true; }
runtime_min="$(echo "${adv_json}" | python3 -c 'import json,sys
try:
    v=json.load(sys.stdin).get("live",{}).get("time_left_minutes")
    print(round(v) if isinstance(v,(int,float)) else "?")
except Exception: print("?")' 2>/dev/null || echo "?")"
shutdown_at="$(echo "${adv_json}" | python3 -c 'import json,sys
try: print(json.load(sys.stdin).get("thresholds",{}).get("shutdown_minutes","?"))
except Exception: print("?")' 2>/dev/null || echo "?")"

# Already shutting down? Do nothing (belt + suspenders on top of systemd's
# oneshot serialization — the sequence takes minutes; the timer must not restack).
if [ -e "${SHUTDOWN_LOCK}" ]; then
  log_info "graceful shutdown already in progress (${SHUTDOWN_LOCK}) — skipping tick"
  exit 0
fi

# Refuse to act on an INDETERMINATE probe state (rc≥2 / error / unknown). This
# guards against a probe crash or python-absent being misread as 'critical'.
if [ "${adv_rc}" -ge 2 ] || [ "${verdict}" = "error" ] || [ "${verdict}" = "unknown" ]; then
  log_error "power probe error (rc=${adv_rc}, verdict=${verdict}) — NOT acting on an indeterminate state (fix the probe)"
  exit 0
fi

# ── ATTENTION: warn the operator minutes ahead — ONCE per transition ───────
if [ "${verdict}" = "attention" ]; then
  if [ "${last_verdict}" != "attention" ] && [ "${last_verdict}" != "critical" ]; then
    log_warn "verdict=attention — UPS on battery, ~${runtime_min} min runtime; graceful shutdown at ${shutdown_at} min"
    _warn approaching "On UPS battery — ~${runtime_min} min runtime left; graceful shutdown fires at ${shutdown_at} min. Save your work."
  else
    log_info "verdict=attention (already warned this episode) — no repeat"
  fi
  _save_verdict
  exit 0
fi

# ── OK / no-ups: nothing to do (record verdict so the next 'attention' warns) ─
if [ "${verdict}" != "critical" ]; then
  log_info "verdict=${verdict} (rc=${adv_rc}) — no shutdown action"
  _save_verdict
  exit 0
fi

# ── CRITICAL (rc=1 + verdict=critical): arm gate, then ORCHESTRATE ─────────
armed_env="${SOVEREIGN_OS_POWER_SHUTDOWN_ARMED:-NO}"
armed_cfg="$(echo "${adv_json}" | python3 -c '
import json, sys
try:
    print("YES" if json.load(sys.stdin).get("thresholds", {}).get("enabled") else "NO")
except Exception:
    print("NO")
')"
if [ "${armed_env}" != "YES" ] && [ "${armed_cfg}" != "YES" ]; then
  log_warn "CRITICAL UPS state but graceful shutdown NOT ARMED — warning only (no poweroff)."
  log_warn "  Arm via power.toml [graceful_shutdown] enabled=true OR SOVEREIGN_OS_POWER_SHUTDOWN_ARMED=YES."
  _warn imminent "UPS CRITICAL (~${runtime_min} min) — auto-shutdown is DISARMED. Shut down manually to avoid data loss."
  _save_verdict
  exit 0
fi

if ! command -v systemctl >/dev/null 2>&1; then
  log_error "systemctl missing — cannot orchestrate shutdown"
  exit 1
fi

# Confirmed critical + armed → run the STAGED graceful soft-exit (announce →
# drain inference / finish in-flight → unload models → stop services → sync →
# poweroff) via the R262 schedule-manifest. This REPLACES the old bare
# `shutdown -h`: services + models exit cleanly, and the operator is warned
# across every medium before AND during.
verdict="critical"; _save_verdict
log_warn "CRITICAL + armed — graceful soft-exit orchestrator engaged (schedule-manifest apply)"
_warn imminent "UPS battery critical (~${runtime_min} min) — graceful shutdown starting now."

if [ -n "${DRY}" ]; then
  log_info "DRY-RUN — orchestrator PLAN (no lock, no poweroff):"
  [ -f "${ORCHESTRATOR}" ] && SOVEREIGN_OS_DRY_RUN=1 python3 "${ORCHESTRATOR}" apply --confirm --dry-run || true
  exit 0
fi

# Real path: mark in-progress (re-entry lock), record the fired metric, then run
# the staged soft-exit to completion (it ends in `systemctl poweroff`).
mkdir -p "$(dirname "${SHUTDOWN_LOCK}")" 2>/dev/null || true
: > "${SHUTDOWN_LOCK}" 2>/dev/null || true
emit_guard_metrics 1
if [ -f "${ORCHESTRATOR}" ]; then
  SOVEREIGN_OS_CONFIRM_DESTROY=YES python3 "${ORCHESTRATOR}" apply --confirm \
    || log_error "schedule-manifest apply reported step failures (see its output above)"
else
  log_error "schedule-manifest.py missing — falling back to bare shutdown(8)"
  shutdown -h "+1" "sovereign-os: UPS battery critical, gracefully powering off" || true
fi
exit 0
