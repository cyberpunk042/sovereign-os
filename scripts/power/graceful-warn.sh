#!/usr/bin/env bash
# scripts/power/graceful-warn.sh — SDD-026 Z-18: warn the operator across EVERY
# medium before AND during a graceful shutdown. A single fan-out point reused by
# the power-shutdown-guard (pre-warnings, minutes ahead) and by the shutdown
# manifest's announce steps (during the soft-exit). "warn the user through all
# the medium possible before that happens and during" (operator, 2026-07-08).
#
# Usage: graceful-warn.sh <stage> <message...>
#   stage ∈ approaching | imminent | executing | final
#
# Mediums (each best-effort, never fatal — a missing tool is skipped):
#   notify send   → file / webhook / ntfy (operator's phone) via R228
#   wall          → every logged-in terminal
#   /dev/console  → the physical console
#   notify-send   → desktop bubbles in active X11/Wayland sessions
#   metric        → sovereign_os_power_graceful_warn_total{stage,severity}
#
# Honors SOVEREIGN_OS_DRY_RUN=1 (logs the fan-out without emitting to humans).
set -uo pipefail
__SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
__REPO_ROOT="$(cd "${__SCRIPT_DIR}/.." && pwd)"
# shellcheck source=../build/lib/common.sh
. "${__REPO_ROOT}/scripts/build/lib/common.sh" 2>/dev/null || {
  log_info() { echo "INFO  [graceful-warn] $*"; }
  log_warn() { echo "WARN  [graceful-warn] $*" >&2; }
}
# shellcheck source=../build/lib/observability.sh
. "${__REPO_ROOT}/scripts/build/lib/observability.sh" 2>/dev/null || emit_metric() { :; }

STAGE="${1:-imminent}"; shift || true
MSG="${*:-graceful shutdown}"
case "${STAGE}" in
  approaching) SEV="attention" ;;
  imminent|executing|final) SEV="down" ;;
  *) SEV="attention"; STAGE="approaching" ;;
esac
BANNER="⚡ SOVEREIGN-OS graceful shutdown [${STAGE}]: ${MSG}"

if [ -n "${SOVEREIGN_OS_DRY_RUN:-}" ]; then
  log_info "DRY-RUN — would fan '${BANNER}' to notify(${SEV}) + wall + console + desktop"
  emit_metric sovereign_os_power_graceful_warn_total 1 "stage=\"${STAGE}\",severity=\"${SEV}\""
  exit 0
fi

# 1. notify fan-out (file/webhook/ntfy → operator's phone), via the R228 send verb
python3 "${__REPO_ROOT}/scripts/notify/dispatch.py" send \
  --severity "${SEV}" --probe "power-shutdown" \
  --title "sovereign-os graceful shutdown (${STAGE})" \
  --message "${MSG}" >/dev/null 2>&1 || log_warn "notify send failed (non-fatal)"

# 2. wall — every logged-in terminal
if command -v wall >/dev/null 2>&1; then
  printf '%s\n' "${BANNER}" | wall 2>/dev/null || true
fi

# 3. the physical console
if [ -w /dev/console ]; then
  printf '%s\n' "${BANNER}" > /dev/console 2>/dev/null || true
fi

# 4. desktop notification bubbles in active graphical sessions (best-effort)
_desktop_notify() {
  command -v notify-send >/dev/null 2>&1 || return 0
  command -v loginctl >/dev/null 2>&1 || return 0
  local urgency; [ "${SEV}" = "down" ] && urgency=critical || urgency=normal
  local sid user uid stype
  while read -r sid _rest; do
    [ -n "${sid}" ] || continue
    stype="$(loginctl show-session "${sid}" -p Type --value 2>/dev/null)"
    [ "${stype}" = "x11" ] || [ "${stype}" = "wayland" ] || continue
    user="$(loginctl show-session "${sid}" -p Name --value 2>/dev/null)"
    uid="$(loginctl show-session "${sid}" -p User --value 2>/dev/null)"
    [ -n "${user}" ] && [ -n "${uid}" ] || continue
    sudo -u "${user}" \
      DISPLAY="${DISPLAY:-:0}" \
      DBUS_SESSION_BUS_ADDRESS="unix:path=/run/user/${uid}/bus" \
      notify-send -u "${urgency}" "⚡ sovereign-os — shutdown ${STAGE}" "${MSG}" \
      2>/dev/null || true
  done < <(loginctl list-sessions --no-legend 2>/dev/null)
}
_desktop_notify

emit_metric sovereign_os_power_graceful_warn_total 1 "stage=\"${STAGE}\",severity=\"${SEV}\""
log_info "warned (${STAGE}): ${MSG}"
exit 0
