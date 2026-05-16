#!/usr/bin/env bash
# scripts/hooks/recurrent/zfs-scrub.sh
#
# Weekly ZFS scrub. Called by systemd timer (Stage 2+ installs the
# timer unit). Idempotent — skips if a scrub is already in progress.

__SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
__REPO_ROOT="$(cd "${__SCRIPT_DIR}/../../.." && pwd)"
# shellcheck source=../../build/lib/common.sh
. "${__REPO_ROOT}/scripts/build/lib/common.sh"
# shellcheck source=../../build/lib/observability.sh
. "${__REPO_ROOT}/scripts/build/lib/observability.sh"

: "${SOVEREIGN_OS_POOL_NAME:=tank}"

log_step_header "zfs-scrub" "weekly ZFS scrub of ${SOVEREIGN_OS_POOL_NAME}"

require_root
require_command zpool

emit_zfs_metrics() {
  # Pool health gauge: 1 if ONLINE, 0 otherwise
  local health=0
  if zpool status "${SOVEREIGN_OS_POOL_NAME}" 2>/dev/null | grep -q "state: ONLINE"; then
    health=1
  fi
  emit_metric_set zfs-pool \
    '# HELP sovereign_os_zfs_pool_health Pool health (1=ONLINE, 0=DEGRADED/UNAVAIL)' \
    '# TYPE sovereign_os_zfs_pool_health gauge' \
    "sovereign_os_zfs_pool_health{pool=\"${SOVEREIGN_OS_POOL_NAME}\"} ${health}" \
    '# HELP sovereign_os_zfs_scrub_last_run_timestamp Unix timestamp of last scrub initiation' \
    '# TYPE sovereign_os_zfs_scrub_last_run_timestamp gauge' \
    "sovereign_os_zfs_scrub_last_run_timestamp{pool=\"${SOVEREIGN_OS_POOL_NAME}\"} $(date +%s)"
}

if ! zpool list "${SOVEREIGN_OS_POOL_NAME}" >/dev/null 2>&1; then
  log_warn "pool ${SOVEREIGN_OS_POOL_NAME} not present; nothing to scrub"
  # Still emit health=0 so dashboards show absence
  emit_metric sovereign_os_zfs_pool_health 0 "pool=\"${SOVEREIGN_OS_POOL_NAME}\""
  exit 0
fi

# Skip if scrub in progress
if zpool status "${SOVEREIGN_OS_POOL_NAME}" | grep -qi "scrub in progress"; then
  log_info "scrub already in progress; skipping new start"
  emit_zfs_metrics
  exit 0
fi

log_info "starting scrub on ${SOVEREIGN_OS_POOL_NAME}"
zpool scrub "${SOVEREIGN_OS_POOL_NAME}"

log_info "scrub started; monitor with 'zpool status ${SOVEREIGN_OS_POOL_NAME}'"
emit_zfs_metrics
