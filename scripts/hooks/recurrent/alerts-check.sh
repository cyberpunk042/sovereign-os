#!/usr/bin/env bash
# scripts/hooks/recurrent/alerts-check.sh
#
# Hourly meta-observability: run `sovereign-osctl alerts --json`,
# count ALERT + WARN entries, emit Layer B metrics so operators get
# a time-series view of "how noisy is my fleet right now?".
#
# Closes the operator-sovereignty loop:
#   Round 87: every metric is documented
#   Round 88: operators can read .prom files via `metrics`
#   Round 89: operators get rule-derived alerts via `alerts`
#   Round 90: alert volume is itself a metric (this hook)
#
# Also persists the alert payload to /var/lib/sovereign-os/alerts.json
# so a freshly-logged-in operator can `cat` it for the current state
# without re-running the rule engine.
#
# Honors SOVEREIGN_OS_DRY_RUN=1.

set -euo pipefail

__SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
__REPO_ROOT="$(cd "${__SCRIPT_DIR}/../../.." && pwd)"
# shellcheck source=../../build/lib/common.sh
. "${__REPO_ROOT}/scripts/build/lib/common.sh"
# shellcheck source=../../build/lib/observability.sh
. "${__REPO_ROOT}/scripts/build/lib/observability.sh"

STEP_ID="alerts-check"

: "${SOVEREIGN_OS_ALERTS_STATE_FILE:=/var/lib/sovereign-os/alerts.json}"

log_step_header "${STEP_ID}" "derive alerts from Layer B + emit meta-counters"

if [ -n "${SOVEREIGN_OS_DRY_RUN:-}" ]; then
  log_info "DRY-RUN — would run 'sovereign-osctl alerts --json' and emit:"
  log_info "  sovereign_os_meta_alert_count{level=\"ALERT\"} <count>"
  log_info "  sovereign_os_meta_alert_count{level=\"WARN\"}  <count>"
  log_info "  sovereign_os_meta_alerts_check_last_run_timestamp <epoch>"
  exit 0
fi

# Locate sovereign-osctl. Use SOVEREIGN_OS_OSCTL if set; otherwise
# search PATH, then fall back to the in-repo path (test contexts).
osctl="${SOVEREIGN_OS_OSCTL:-}"
if [ -z "${osctl}" ]; then
  if command -v sovereign-osctl >/dev/null 2>&1; then
    osctl="$(command -v sovereign-osctl)"
  elif [ -x "${__REPO_ROOT}/scripts/sovereign-osctl" ]; then
    osctl="${__REPO_ROOT}/scripts/sovereign-osctl"
  else
    log_error "cannot locate sovereign-osctl"
    exit 1
  fi
fi

# Collect the alert payload. cmd_alerts exits 1 when ALERTs are present,
# but that's a signalling exit not an error — capture it without
# tripping `set -e`.
set +e
alerts_json="$("${osctl}" alerts --json 2>/dev/null)"
osctl_rc=$?
set -e

# Empty or malformed → treat as no alerts (still emit zero counters so
# the metric is always present, never just disappears)
if [ -z "${alerts_json}" ] || ! python3 -c "import json,sys; json.loads(sys.stdin.read())" <<< "${alerts_json}" >/dev/null 2>&1; then
  log_warn "alerts --json returned no parseable output (rc=${osctl_rc}); emitting zero counters"
  alerts_json="[]"
fi

# Persist for offline operator inspection. Dir creation may fail in
# unprivileged contexts — that's fine, the metrics still ship.
mkdir -p "$(dirname "${SOVEREIGN_OS_ALERTS_STATE_FILE}")" 2>/dev/null || true
if [ -w "$(dirname "${SOVEREIGN_OS_ALERTS_STATE_FILE}")" ] 2>/dev/null; then
  printf '%s\n' "${alerts_json}" > "${SOVEREIGN_OS_ALERTS_STATE_FILE}"
  log_info "alert payload persisted: ${SOVEREIGN_OS_ALERTS_STATE_FILE}"
fi

# Tally by level
alert_count="$(python3 -c "
import json, sys
data = json.loads(sys.stdin.read())
print(sum(1 for a in data if a.get('level') == 'ALERT'))
" <<< "${alerts_json}")"
warn_count="$(python3 -c "
import json, sys
data = json.loads(sys.stdin.read())
print(sum(1 for a in data if a.get('level') == 'WARN'))
" <<< "${alerts_json}")"

log_info "  ALERT count: ${alert_count}"
log_info "  WARN  count: ${warn_count}"

# Emit as one atomic .prom file so the snapshot is consistent
emit_metric_set alerts-check \
  '# HELP sovereign_os_meta_alert_count Alerts derived from Layer B rule engine, grouped by level' \
  '# TYPE sovereign_os_meta_alert_count gauge' \
  "sovereign_os_meta_alert_count{level=\"ALERT\"} ${alert_count}" \
  "sovereign_os_meta_alert_count{level=\"WARN\"} ${warn_count}" \
  '# HELP sovereign_os_meta_alerts_check_last_run_timestamp Unix epoch of last alerts-check run' \
  '# TYPE sovereign_os_meta_alerts_check_last_run_timestamp gauge' \
  "sovereign_os_meta_alerts_check_last_run_timestamp $(date +%s)"

log_info "${STEP_ID}: complete"
