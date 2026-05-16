#!/usr/bin/env bash
# scripts/hooks/recurrent/thermal-watch.sh
#
# Recurrent thermal monitoring (R172) — invoked every 5 minutes by
# sovereign-thermal-watch.timer. Wraps scripts/hardware/thermal-watch.py
# with the right env + paths so the systemd unit stays simple.
#
# Honors SOVEREIGN_OS_DRY_RUN=1.

set -euo pipefail

__SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
__REPO_ROOT="$(cd "${__SCRIPT_DIR}/../../.." && pwd)"
# shellcheck source=../../build/lib/common.sh
. "${__REPO_ROOT}/scripts/build/lib/common.sh"

STEP_ID="thermal-watch"
log_step_header "${STEP_ID}" "per-sensor thermal threshold check + Layer B emission"

# Profile resolution: the active-profile.env exports SOVEREIGN_OS_PROFILE_ID;
# fall back to sain-01 if absent (matches script default).
if [ -f /etc/sovereign-os/active-profile.env ]; then
  # shellcheck source=/dev/null
  . /etc/sovereign-os/active-profile.env
fi
: "${SOVEREIGN_OS_PROFILE_ID:=sain-01}"

if [ -n "${SOVEREIGN_OS_DRY_RUN:-}" ]; then
  log_info "DRY-RUN — would invoke thermal-watch.py --profile=${SOVEREIGN_OS_PROFILE_ID} --emit-metrics"
  exit 0
fi

# Don't fail the timer when sensors hit WARN/CRITICAL — the metric +
# the JSONL event are the report channels. The hook log line below
# only fires when the script can't run AT ALL (missing python, broken
# fs, etc).
if ! python3 "${__REPO_ROOT}/scripts/hardware/thermal-watch.py" \
    --profile "${SOVEREIGN_OS_PROFILE_ID}" \
    --emit-metrics >/dev/null; then
  rc=$?
  case "${rc}" in
    1|2)
      # Thresholds breached — normal operational output, not a hook failure.
      ;;
    *)
      log_warn "thermal-watch.py failed with rc=${rc}"
      exit "${rc}"
      ;;
  esac
fi

exit 0
